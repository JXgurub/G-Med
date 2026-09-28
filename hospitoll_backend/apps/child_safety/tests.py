from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.http import HttpResponse
from django.test import RequestFactory
from rest_framework.test import APITestCase
from unittest.mock import patch

from core.error_logging import ErrorLoggingMiddleware
from apps.site_settings.models import SystemAlert
from .models import SafetyRegion, SafetyVote, SafetyVoteAudit
from .views import ChildSafetyVoteThrottle


User = get_user_model()


class ChildSafetyApiTests(APITestCase):
    def setUp(self):
        self.region = SafetyRegion.objects.create(name='Test Viloyati', level=SafetyRegion.Level.REGION)
        self.district = SafetyRegion.objects.create(
            name='Test Tumani',
            level=SafetyRegion.Level.DISTRICT,
            parent=self.region,
        )
        self.user = User.objects.create_user(
            username='safety-voter',
            email='safety-voter@example.test',
            password='test-password-123',
            role='patient',
        )
        self.admin = User.objects.create_user(
            username='safety-admin',
            email='safety-admin@example.test',
            password='test-password-123',
            role='admin',
            is_staff=True,
        )

    def test_anonymous_user_cannot_vote(self):
        response = self.client.post('/api/v1/child-safety/vote/', {
            'region_id': str(self.district.id),
            'choice': SafetyVote.Choice.SAFE,
        })

        self.assertEqual(response.status_code, 401)
        self.assertEqual(SafetyVote.objects.count(), 0)

    def test_authenticated_user_can_vote_only_once_per_region(self):
        self.client.force_authenticate(self.user)
        payload = {'region_id': str(self.district.id), 'choice': SafetyVote.Choice.SAFE}

        first_response = self.client.post('/api/v1/child-safety/vote/', payload)
        second_response = self.client.post('/api/v1/child-safety/vote/', payload)

        self.assertEqual(first_response.status_code, 201)
        self.assertEqual(second_response.status_code, 409)
        self.assertEqual(SafetyVote.objects.filter(is_active=True).count(), 1)
        self.assertEqual(SafetyVoteAudit.objects.filter(action=SafetyVoteAudit.Action.CAST).count(), 1)

    def test_vote_endpoint_is_rate_limited_per_authenticated_user(self):
        cache.clear()
        self.client.force_authenticate(self.user)
        first_region = {'region_id': str(self.region.id), 'choice': SafetyVote.Choice.SAFE}
        second_region = {'region_id': str(self.district.id), 'choice': SafetyVote.Choice.CAUTION}

        with patch.dict(ChildSafetyVoteThrottle.THROTTLE_RATES, {'child_safety_vote': '1/hour'}):
            first_response = self.client.post('/api/v1/child-safety/vote/', first_region)
            limited_response = self.client.post('/api/v1/child-safety/vote/', second_region)

        self.assertEqual(first_response.status_code, 201)
        self.assertEqual(limited_response.status_code, 429)
        self.assertEqual(SafetyVote.objects.filter(user=self.user).count(), 1)

    def test_vote_endpoint_error_audit_does_not_persist_ip_address(self):
        request = RequestFactory().post(
            '/api/v1/child-safety/vote/',
            REMOTE_ADDR='192.0.2.20',
        )
        request.user = self.user
        middleware = ErrorLoggingMiddleware(lambda _request: HttpResponse(status=429))

        middleware(request)

        alert = SystemAlert.objects.get(alert_type='http_error')
        self.assertIsNone(alert.context['remote_ip'])
        self.assertEqual(str(alert.context['user_id']), str(self.user.id))

    def test_statistics_use_weighted_community_score_and_count_only_active_votes(self):
        voters = [
            User.objects.create_user(
                username=f'score-voter-{index}',
                email=f'score-voter-{index}@example.test',
                password='test-password-123',
                role='patient',
            )
            for index in range(3)
        ]
        choices = [SafetyVote.Choice.SAFE, SafetyVote.Choice.CAUTION, SafetyVote.Choice.DANGER]
        for voter, choice in zip(voters, choices):
            SafetyVote.objects.create(region=self.district, user=voter, choice=choice)

        response = self.client.get(f'/api/v1/child-safety/statistics/{self.district.id}/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['community_score'], 5.0)
        self.assertEqual(response.data['safe_votes'], 1)
        self.assertEqual(response.data['caution_votes'], 1)
        self.assertEqual(response.data['danger_votes'], 1)
        self.assertEqual(response.data['total_votes'], 3)
        self.assertEqual(response.data['official_data'], None)
        self.assertEqual(response.data['final_index'], None)

    def test_authenticated_voter_sees_their_vote_state(self):
        SafetyVote.objects.create(region=self.district, user=self.user, choice=SafetyVote.Choice.CAUTION)
        self.client.force_authenticate(self.user)

        response = self.client.get(f'/api/v1/child-safety/statistics/{self.district.id}/')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['has_voted'])
        self.assertEqual(response.data['my_vote_choice'], SafetyVote.Choice.CAUTION)

    def test_admin_can_add_valid_child_region_but_not_wrong_parent_level(self):
        self.client.force_authenticate(self.admin)
        endpoint = '/api/v1/child-safety/admin/regions/'

        invalid_response = self.client.post(endpoint, {
            'name': 'Xato Mahalla',
            'level': SafetyRegion.Level.MAHALLA,
            'parent_id': str(self.region.id),
        })
        valid_response = self.client.post(endpoint, {
            'name': 'Yangi Mahalla',
            'level': SafetyRegion.Level.MAHALLA,
            'parent_id': str(self.district.id),
        })

        self.assertEqual(invalid_response.status_code, 400)
        self.assertEqual(valid_response.status_code, 201)
        self.assertEqual(valid_response.data['name'], 'Yangi Mahalla')

    def test_admin_moderation_requires_reason_and_writes_audit(self):
        vote = SafetyVote.objects.create(region=self.district, user=self.user, choice=SafetyVote.Choice.DANGER)
        self.client.force_authenticate(self.admin)
        endpoint = f'/api/v1/child-safety/admin/votes/{vote.id}/revoke/'

        missing_reason = self.client.post(endpoint, {
            'reason_category': SafetyVoteAudit.ReasonCategory.FRAUD,
            'reason': 'spam',
        })
        invalid_category = self.client.post(endpoint, {
            'reason_category': 'other',
            'reason': 'Yetarlicha uzun izoh, lekin ruxsat etilmagan toifa.',
        })
        revoked = self.client.post(endpoint, {
            'reason_category': SafetyVoteAudit.ReasonCategory.FRAUD,
            'reason': 'Takroriy avtomatlashtirilgan ovoz aniqlandi.',
        })

        self.assertEqual(missing_reason.status_code, 400)
        self.assertEqual(invalid_category.status_code, 400)
        self.assertEqual(revoked.status_code, 200)
        vote.refresh_from_db()
        self.assertFalse(vote.is_active)
        self.assertEqual(vote.revoked_by, self.admin)
        self.assertEqual(SafetyVoteAudit.objects.filter(action=SafetyVoteAudit.Action.REVOKE).count(), 1)
        self.assertEqual(
            SafetyVoteAudit.objects.get(action=SafetyVoteAudit.Action.REVOKE).reason_category,
            SafetyVoteAudit.ReasonCategory.FRAUD,
        )
        self.assertEqual(revoked.data['statistics']['total_votes'], 0)

    def test_non_admin_cannot_manage_regions_or_votes(self):
        self.client.force_authenticate(self.user)

        response = self.client.get('/api/v1/child-safety/admin/regions/')

        self.assertEqual(response.status_code, 403)

    def test_admin_can_permanently_delete_empty_leaf_region(self):
        self.client.force_authenticate(self.admin)

        response = self.client.delete(f'/api/v1/child-safety/admin/regions/{self.district.id}/')

        self.assertEqual(response.status_code, 204)
        self.assertFalse(SafetyRegion.objects.filter(id=self.district.id).exists())
        self.assertTrue(SafetyRegion.objects.filter(id=self.region.id).exists())

    def test_admin_archives_regions_with_votes_and_preserves_vote_history(self):
        SafetyRegion.objects.create(
            name='Test Mahallasi',
            level=SafetyRegion.Level.MAHALLA,
            parent=self.district,
        )
        vote = SafetyVote.objects.create(
            region=self.district,
            user=self.user,
            choice=SafetyVote.Choice.SAFE,
        )
        self.client.force_authenticate(self.admin)

        response = self.client.delete(f'/api/v1/child-safety/admin/regions/{self.region.id}/')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['archived'])
        self.assertEqual(response.data['archived_region_count'], 3)
        self.assertTrue(SafetyRegion.objects.filter(id=self.region.id, is_active=False).exists())
        self.assertTrue(SafetyRegion.objects.filter(id=self.district.id, is_active=False).exists())
        self.assertTrue(SafetyVote.objects.filter(id=vote.id, is_active=True).exists())
