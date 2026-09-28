from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from .models import SafetyRegion, SafetyVote, SafetyVoteAudit
from .serializers import (
    AdminSafetyRegionSerializer,
    AdminSafetyVoteSerializer,
    SafetyRegionCreateSerializer,
    SafetyRegionDetailSerializer,
    SafetyRegionSerializer,
    SafetyVoteCreateSerializer,
    SafetyVoteRevokeSerializer,
)
from .services import get_admin_region_statistics, get_region_statistics


class IsAdministrator(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (user.is_superuser or getattr(user, 'is_administrator', False))
        )


class ChildSafetyVoteThrottle(UserRateThrottle):
    scope = 'child_safety_vote'


class RegionListView(APIView):
    permission_classes = (AllowAny,)

    def get(self, request):
        parent_id = request.query_params.get('parent_id')
        regions = SafetyRegion.objects.filter(is_active=True).select_related('parent')
        if parent_id:
            regions = regions.filter(parent_id=parent_id)
        else:
            regions = regions.filter(parent__isnull=True)
        return Response(SafetyRegionSerializer(regions, many=True).data)


class RegionDetailView(APIView):
    permission_classes = (AllowAny,)

    def get(self, request, region_id):
        region = get_object_or_404(
            SafetyRegion.objects.prefetch_related('children'),
            id=region_id,
            is_active=True,
        )
        return Response(SafetyRegionDetailSerializer(region).data)


class RegionStatisticsView(APIView):
    permission_classes = (AllowAny,)

    def get(self, request, region_id):
        region = get_object_or_404(SafetyRegion, id=region_id, is_active=True)
        data = {
            'region': SafetyRegionSerializer(region).data,
            **get_region_statistics(region),
        }
        if request.user.is_authenticated:
            prior_vote = SafetyVote.objects.filter(
                region=region,
                user=request.user,
            ).first()
            data['has_voted'] = prior_vote is not None
            data['my_vote_choice'] = prior_vote.choice if prior_vote else None
        return Response(data)


class VoteCreateView(APIView):
    permission_classes = (IsAuthenticated,)
    throttle_classes = (ChildSafetyVoteThrottle,)

    def post(self, request):
        serializer = SafetyVoteCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        region = serializer.region
        choice = serializer.validated_data['choice']

        try:
            with transaction.atomic():
                vote = SafetyVote.objects.create(
                    region=region,
                    user=request.user,
                    choice=choice,
                )
                SafetyVoteAudit.objects.create(
                    region=region,
                    vote=vote,
                    actor=request.user,
                    action=SafetyVoteAudit.Action.CAST,
                    choice=choice,
                )
        except IntegrityError:
            return Response(
                {'detail': 'Siz bu hudud uchun allaqachon ovoz bergansiz.'},
                status=status.HTTP_409_CONFLICT,
            )

        return Response({
            'detail': 'Ovozingiz qabul qilindi.',
            'statistics': get_region_statistics(region),
        }, status=status.HTTP_201_CREATED)


class AdminRegionListCreateView(APIView):
    permission_classes = (IsAuthenticated, IsAdministrator)

    def get(self, request):
        regions = get_admin_region_statistics()
        return Response(AdminSafetyRegionSerializer(regions, many=True).data)

    def post(self, request):
        serializer = SafetyRegionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        region = serializer.save()
        return Response(SafetyRegionSerializer(region).data, status=status.HTTP_201_CREATED)


class AdminRegionDeleteView(APIView):
    permission_classes = (IsAuthenticated, IsAdministrator)

    def delete(self, request, region_id):
        with transaction.atomic():
            region = get_object_or_404(SafetyRegion.objects.select_for_update(), id=region_id)
            subtree = [region]
            for current in subtree:
                subtree.extend(
                    SafetyRegion.objects.select_for_update().filter(parent=current)
                )

            region_ids = [item.id for item in subtree]
            has_history = (
                SafetyVote.objects.filter(region_id__in=region_ids).exists()
                or SafetyVoteAudit.objects.filter(region_id__in=region_ids).exists()
            )

            if len(subtree) > 1 or has_history:
                SafetyRegion.objects.filter(id__in=region_ids, is_active=True).update(
                    is_active=False,
                    updated_at=timezone.now(),
                )
                return Response({
                    'detail': 'Hududdagi ovozlar yoki quyi hududlar saqlanib, arxivlandi.',
                    'archived': True,
                    'archived_region_count': len(region_ids),
                })

            region.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)


class AdminRegionVotesView(APIView):
    permission_classes = (IsAuthenticated, IsAdministrator)

    def get(self, request, region_id):
        region = get_object_or_404(SafetyRegion, id=region_id)
        votes = SafetyVote.objects.filter(region=region, is_active=True).order_by('-created_at')[:200]
        return Response(AdminSafetyVoteSerializer(votes, many=True).data)


class AdminVoteRevokeView(APIView):
    permission_classes = (IsAuthenticated, IsAdministrator)

    def post(self, request, vote_id):
        serializer = SafetyVoteRevokeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            vote = get_object_or_404(SafetyVote.objects.select_for_update(), id=vote_id)
            if not vote.is_active:
                return Response(
                    {'detail': 'Bu ovoz avval bekor qilingan.'},
                    status=status.HTTP_409_CONFLICT,
                )
            vote.is_active = False
            vote.revoked_at = timezone.now()
            vote.revoked_by = request.user
            vote.revoke_reason = serializer.validated_data['reason']
            vote.save(update_fields=('is_active', 'revoked_at', 'revoked_by', 'revoke_reason'))
            SafetyVoteAudit.objects.create(
                region=vote.region,
                vote=vote,
                actor=request.user,
                action=SafetyVoteAudit.Action.REVOKE,
                choice=vote.choice,
                reason_category=serializer.validated_data['reason_category'],
                reason=vote.revoke_reason,
            )

        return Response({
            'detail': 'Ovoz moderatorlik auditi bilan bekor qilindi.',
            'statistics': get_region_statistics(vote.region),
        })
