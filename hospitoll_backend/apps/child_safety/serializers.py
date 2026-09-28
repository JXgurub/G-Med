from rest_framework import serializers

from .models import SafetyRegion, SafetyVote, SafetyVoteAudit
from .services import calculate_community_score, get_region_statistics


class SafetyRegionSerializer(serializers.ModelSerializer):
    parent_name = serializers.CharField(source='parent.name', read_only=True, default=None)

    class Meta:
        model = SafetyRegion
        fields = ('id', 'name', 'level', 'parent', 'parent_name')


class SafetyRegionDetailSerializer(SafetyRegionSerializer):
    children = SafetyRegionSerializer(many=True, read_only=True)
    statistics = serializers.SerializerMethodField()

    class Meta(SafetyRegionSerializer.Meta):
        fields = SafetyRegionSerializer.Meta.fields + ('children', 'statistics')

    def get_statistics(self, region):
        return get_region_statistics(region)


class SafetyVoteCreateSerializer(serializers.Serializer):
    region_id = serializers.UUIDField()
    choice = serializers.ChoiceField(choices=SafetyVote.Choice.choices)

    def validate_region_id(self, value):
        try:
            self.region = SafetyRegion.objects.get(id=value, is_active=True)
        except SafetyRegion.DoesNotExist as exc:
            raise serializers.ValidationError('Tanlangan hudud topilmadi yoki faol emas.') from exc
        return value


class SafetyRegionCreateSerializer(serializers.ModelSerializer):
    parent_id = serializers.PrimaryKeyRelatedField(
        source='parent',
        queryset=SafetyRegion.objects.filter(is_active=True),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = SafetyRegion
        fields = ('id', 'name', 'level', 'parent_id', 'is_active', 'created_at')
        read_only_fields = ('id', 'is_active', 'created_at')

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Hudud nomi kiritilishi shart.')
        return value

    def validate(self, attrs):
        level = attrs['level']
        parent = attrs.get('parent')
        expected_parent_level = {
            SafetyRegion.Level.REGION: None,
            SafetyRegion.Level.DISTRICT: SafetyRegion.Level.REGION,
            SafetyRegion.Level.MAHALLA: SafetyRegion.Level.DISTRICT,
        }[level]
        if (parent.level if parent else None) != expected_parent_level:
            raise serializers.ValidationError({'parent_id': 'Hudud turi va yuqori hudud mos kelmaydi.'})
        duplicate_query = SafetyRegion.objects.filter(
            parent=parent,
            level=level,
            name__iexact=attrs['name'],
        )
        if duplicate_query.exists():
            raise serializers.ValidationError({'name': 'Bu hudud ushbu ota-hududda allaqachon mavjud.'})
        return attrs


class AdminSafetyRegionSerializer(SafetyRegionSerializer):
    parent_id = serializers.UUIDField(read_only=True)
    safe_votes = serializers.IntegerField(read_only=True)
    caution_votes = serializers.IntegerField(read_only=True)
    danger_votes = serializers.IntegerField(read_only=True)
    last_vote_at = serializers.DateTimeField(read_only=True, allow_null=True)
    active_child_count = serializers.IntegerField(read_only=True)
    community_score = serializers.SerializerMethodField()
    total_votes = serializers.SerializerMethodField()

    class Meta(SafetyRegionSerializer.Meta):
        fields = SafetyRegionSerializer.Meta.fields + (
            'parent_id', 'safe_votes', 'caution_votes', 'danger_votes',
            'last_vote_at', 'active_child_count', 'community_score', 'total_votes',
        )

    def get_community_score(self, region):
        return calculate_community_score({
            'safe': region.safe_votes,
            'caution': region.caution_votes,
            'danger': region.danger_votes,
        })['community_score']

    def get_total_votes(self, region):
        return region.safe_votes + region.caution_votes + region.danger_votes


class AdminSafetyVoteSerializer(serializers.ModelSerializer):
    region_name = serializers.CharField(source='region.name', read_only=True)

    class Meta:
        model = SafetyVote
        fields = ('id', 'region_id', 'region_name', 'choice', 'created_at')


class SafetyVoteRevokeSerializer(serializers.Serializer):
    reason_category = serializers.ChoiceField(choices=SafetyVoteAudit.ReasonCategory.choices)
    reason = serializers.CharField(min_length=10, max_length=1000, trim_whitespace=True)
