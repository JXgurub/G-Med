from django_celery_beat.models import PeriodicTask
qs = PeriodicTask.objects.filter(enabled=True).order_by('name')
print('ENABLED_TASKS', qs.count())
for t in qs:
    print(f"{t.name} | task={t.task} | last_run_at={t.last_run_at} | total={t.total_run_count}")