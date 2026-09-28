from django.urls import path

from .views import (
    AdminRegionListCreateView,
    AdminRegionDeleteView,
    AdminRegionVotesView,
    AdminVoteRevokeView,
    RegionDetailView,
    RegionListView,
    RegionStatisticsView,
    VoteCreateView,
)

urlpatterns = [
    path('regions/', RegionListView.as_view(), name='child-safety-regions'),
    path('regions/<uuid:region_id>/', RegionDetailView.as_view(), name='child-safety-region-detail'),
    path('vote/', VoteCreateView.as_view(), name='child-safety-vote'),
    path('statistics/<uuid:region_id>/', RegionStatisticsView.as_view(), name='child-safety-statistics'),
    path('admin/regions/', AdminRegionListCreateView.as_view(), name='child-safety-admin-regions'),
    path('admin/regions/<uuid:region_id>/', AdminRegionDeleteView.as_view(), name='child-safety-admin-region-delete'),
    path('admin/regions/<uuid:region_id>/votes/', AdminRegionVotesView.as_view(), name='child-safety-admin-region-votes'),
    path('admin/votes/<uuid:vote_id>/revoke/', AdminVoteRevokeView.as_view(), name='child-safety-admin-vote-revoke'),
]
