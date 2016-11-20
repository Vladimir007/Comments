from django.contrib.auth.models import User
from django.db import models
from Comments.vars import OBJECT_TYPES, COMMENT_HISTORY_TYPE


class BlogPost(models.Model):
    name = models.CharField(max_length=100)


class UserPage(models.Model):
    name = models.CharField(max_length=100)


class AnotherObject(models.Model):
    name = models.CharField(max_length=100)


class CommentRoot(models.Model):
    obj_type = models.CharField(max_length=1, choices=OBJECT_TYPES, db_index=True)
    obj_id = models.PositiveIntegerField(db_index=True)

    class Meta:
        db_table = 'comment_root'


class Comment(models.Model):
    root = models.ForeignKey(CommentRoot)
    author = models.ForeignKey(User)
    parent = models.ForeignKey('self', null=True, related_name='children')
    date = models.DateTimeField(auto_now_add=True)
    last_change = models.DateTimeField(auto_now=True)
    text = models.TextField()


class CommentHistory(models.Model):
    comment = models.ForeignKey(Comment, null=True, on_delete=models.SET_NULL, related_name='history')
    author = models.ForeignKey(User)
    old_text = models.TextField(null=True)
    new_text = models.TextField(null=True)
    date = models.DateTimeField(db_index=True)


class DownloadHistory(models.Model):
    user = models.ForeignKey(User)
    target = models.ForeignKey(User, related_name='+')
    date = models.DateTimeField(auto_now=True)
    min_date = models.DateTimeField()
    max_date = models.DateTimeField()
    file_type = models.CharField(max_length=1, choices=COMMENT_HISTORY_TYPE)
