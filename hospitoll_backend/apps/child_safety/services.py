from django.db.models import Count, Max, Q

from .models import SafetyRegion, SafetyVote


VOTE_WEIGHTS = {
    SafetyVote.Choice.SAFE: 10,
    SafetyVote.Choice.CAUTION: 5,
    SafetyVote.Choice.DANGER: 0,
}


def calculate_community_score(votes):
    safe_votes = votes.get(SafetyVote.Choice.SAFE, 0)
    caution_votes = votes.get(SafetyVote.Choice.CAUTION, 0)
    danger_votes = votes.get(SafetyVote.Choice.DANGER, 0)
    total_votes = safe_votes + caution_votes + danger_votes
    score = None
    if total_votes:
        score = round((safe_votes * 10 + caution_votes * 5) / total_votes, 1)

    return {
        'community_score': score,
        'score_label': 'Jamoatchilik bahosi',
        'safe_votes': safe_votes,
        'caution_votes': caution_votes,
        'danger_votes': danger_votes,
        'total_votes': total_votes,
        'last_vote_at': votes.get('last_vote_at'),
        'score_method': {
            'safe': VOTE_WEIGHTS[SafetyVote.Choice.SAFE],
            'caution': VOTE_WEIGHTS[SafetyVote.Choice.CAUTION],
            'danger': VOTE_WEIGHTS[SafetyVote.Choice.DANGER],
            'formula': '(xavfsiz * 10 + ehtiyot * 5 + muammo * 0) / jami ovoz',
        },
        'official_data': None,
        'final_index': None,
    }


def get_region_statistics(region):
    rows = region.votes.filter(is_active=True).aggregate(
        safe_votes=Count('id', filter=Q(choice=SafetyVote.Choice.SAFE)),
        caution_votes=Count('id', filter=Q(choice=SafetyVote.Choice.CAUTION)),
        danger_votes=Count('id', filter=Q(choice=SafetyVote.Choice.DANGER)),
        last_vote_at=Max('created_at'),
    )
    return calculate_community_score({
        'safe': rows['safe_votes'],
        'caution': rows['caution_votes'],
        'danger': rows['danger_votes'],
        'last_vote_at': rows['last_vote_at'],
    })


def get_admin_region_statistics():
    return SafetyRegion.objects.filter(is_active=True).annotate(
        safe_votes=Count('votes', distinct=True, filter=Q(votes__is_active=True, votes__choice=SafetyVote.Choice.SAFE)),
        caution_votes=Count('votes', distinct=True, filter=Q(votes__is_active=True, votes__choice=SafetyVote.Choice.CAUTION)),
        danger_votes=Count('votes', distinct=True, filter=Q(votes__is_active=True, votes__choice=SafetyVote.Choice.DANGER)),
        last_vote_at=Max('votes__created_at', filter=Q(votes__is_active=True)),
        active_child_count=Count('children', filter=Q(children__is_active=True), distinct=True),
    ).order_by('level', 'name')
