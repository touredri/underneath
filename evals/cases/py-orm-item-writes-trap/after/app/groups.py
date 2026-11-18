from django.db import models

LIMIT = 100


def add_to_groups(user, groups):
    for group in groups:
        group.members.add(user)


def collect_tags(posts):
    seen = set()
    for post in posts:
        seen.add(post.tag)
    return seen


def bulk_archive():
    Report.objects.filter(archived=False).update(archived=True)
