from django.db import models

LIMIT = 100


def add_to_active_groups(user):
    for group in Group.objects.filter(active=True):
        group.members.add(user)


def archive_all():
    for report in Report.objects.all().iterator():
        report.archived = True
        report.save()
