import json
from io import BytesIO
from django.test import TestCase
from django.test import Client
from django.utils.timezone import now
from main.models import *


class TestApi(TestCase):
    def setUp(self):
        super(TestApi, self).setUp()
        self.author = User.objects.get_or_create(username='test')[0]
        self.author.set_password('1234')
        self.author.save()
        self.client = Client()
        self.ids = [
            BlogPost.objects.get_or_create(name='Blog post')[0].pk,
            UserPage.objects.get_or_create(name='User page')[0].pk,
            AnotherObject.objects.get_or_create(name='Another object')[0].pk
        ]
        self.client.post('/login/', {'username': 'test', 'password': '1234'})

    def test_1_creation(self):
        res = self.client.post('/create_comment/', {'obj_type': '0', 'obj_id': self.ids[0], 'text': 'Comment 1'})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'application/json')
        self.assertNotIn('error', json.loads(str(res.content, encoding='utf8')))
        root = CommentRoot.objects.filter(obj_type='0', obj_id=self.ids[0]).first()
        self.assertIsNotNone(root)
        all_comments = Comment.objects.all()
        self.assertEqual(len(all_comments), 1)
        comment = all_comments.first()
        self.assertIsNotNone(comment)
        self.assertEqual(comment.author, self.author)
        self.assertIsNone(comment.parent)
        self.assertEqual(comment.text, 'Comment 1')

        all_changes = CommentHistory.objects.order_by('-date')
        self.assertEqual(len(all_changes), 1)
        change = all_changes.first()
        self.assertEqual(change.comment, comment)
        self.assertEqual(change.author, self.author)
        self.assertIsNone(change.old_text)
        self.assertEqual(change.new_text, 'Comment 1')
        self.assertEqual(change.date, comment.last_change)

        res = self.client.post('/create_comment/', {'obj_type': 'c', 'obj_id': comment.pk, 'text': 'Comment 2'})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'application/json')
        self.assertNotIn('error', json.loads(str(res.content, encoding='utf8')))
        root = CommentRoot.objects.filter(obj_type='0', obj_id=self.ids[0]).first()
        self.assertIsNotNone(root)
        comment2 = Comment.objects.filter(root=root).order_by('-date').first()
        self.assertIsNotNone(comment2)
        self.assertEqual(comment2.author, self.author)
        self.assertEqual(comment2.parent, comment)
        self.assertEqual(comment2.text, 'Comment 2')

        change = CommentHistory.objects.order_by('-date').first()
        self.assertEqual(change.comment, comment2)
        self.assertEqual(change.author, self.author)
        self.assertIsNone(change.old_text)
        self.assertEqual(change.new_text, 'Comment 2')
        self.assertEqual(change.date, comment2.last_change)

    def test_2_change(self):
        self.client.post('/create_comment/', {'obj_type': '1', 'obj_id': self.ids[1], 'text': 'Comment 1'})
        comments = Comment.objects.all()
        self.assertEqual(len(comments), 1)
        comment = comments.first()

        res = self.client.post('/change_comment/', {'comment_id': comment.pk, 'text': 'New comment'})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'application/json')
        self.assertNotIn('error', json.loads(str(res.content, encoding='utf8')))
        comment = Comment.objects.get(pk=comment.pk)
        self.assertEqual(comment.author, self.author)
        self.assertIsNone(comment.parent)
        self.assertEqual(comment.text, 'New comment')

        all_changes = CommentHistory.objects.order_by('-date')
        self.assertEqual(len(all_changes), 2)
        change = all_changes.first()
        self.assertEqual(change.comment, comment)
        self.assertEqual(change.author, self.author)
        self.assertEqual(change.old_text, 'Comment 1')
        self.assertEqual(change.new_text, 'New comment')
        self.assertEqual(change.date, comment.last_change)

    def test_3_delete(self):
        self.client.post('/create_comment/', {'obj_type': '1', 'obj_id': self.ids[1], 'text': 'Comment 1'})
        comment1 = Comment.objects.get()
        self.client.post('/create_comment/', {'obj_type': 'c', 'obj_id': comment1.pk, 'text': 'Comment 2'})
        comment2 = Comment.objects.get(parent=comment1)

        res = self.client.post('/delete_comment/', {'comment_id': comment1.pk})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'application/json')
        self.assertIn('error', json.loads(str(res.content, encoding='utf8')))
        self.assertEqual(len(Comment.objects.all()), 2)

        res = self.client.post('/delete_comment/', {'comment_id': comment2.pk})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'application/json')
        self.assertNotIn('error', json.loads(str(res.content, encoding='utf8')))
        self.assertEqual(len(Comment.objects.all()), 1)
        self.assertEqual(len(Comment.objects.filter(pk=comment1.pk)), 1)

        all_changes = CommentHistory.objects.order_by('-date')
        self.assertEqual(len(all_changes), 3)
        change = all_changes.first()
        self.assertIsNone(change.comment, None)
        self.assertEqual(change.author, self.author)
        self.assertEqual(change.old_text, 'Comment 2')
        self.assertIsNone(change.new_text)

    def test_4_first_level(self):
        # 1[], 2[3, 4[5]], None
        self.client.post('/create_comment/', {'obj_type': '0', 'obj_id': self.ids[0], 'text': 'Comment 1'})
        self.client.post('/create_comment/', {'obj_type': '1', 'obj_id': self.ids[1], 'text': 'Comment 2'})
        comment = Comment.objects.order_by('-date').first()
        self.client.post('/create_comment/', {'obj_type': 'c', 'obj_id': comment.pk, 'text': 'Comment 3'})
        self.client.post('/create_comment/', {'obj_type': 'c', 'obj_id': comment.pk, 'text': 'Comment 4'})
        comment = Comment.objects.order_by('-date').first()
        self.client.post('/create_comment/', {'obj_type': 'c', 'obj_id': comment.pk, 'text': 'Comment 5'})
        comments = Comment.objects.order_by('date')

        res = self.client.get('/first_level/1/', {'obj': self.ids[0], 'type': '0'})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'application/json')
        content = json.loads(str(res.content, encoding='utf8'))
        self.assertNotIn('error', content)
        comment_list = json.loads(content['comments'])
        self.assertEqual(comment_list, [[1, {'text': 'Comment 1'}]])

        res = self.client.get('/first_level/1/', {'obj': comments[1].pk, 'type': 'c'})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'application/json')
        content = json.loads(str(res.content, encoding='utf8'))
        self.assertNotIn('error', content)
        comment_list = json.loads(content['comments'])
        self.assertEqual(comment_list, [[1, {'text': 'Comment 3'}], [2, {'text': 'Comment 4'}]])

        res = self.client.get('/first_level/1/', {'obj': self.ids[2], 'type': '2'})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'application/json')
        content = json.loads(str(res.content, encoding='utf8'))
        self.assertNotIn('error', content)
        comment_list = json.loads(content['comments'])
        self.assertEqual(comment_list, [])

    def test_5_tree(self):
        # 1[2, 3], 4[5, 6[7]], None
        self.client.post('/create_comment/', {'obj_type': '0', 'obj_id': self.ids[0], 'text': 'Comment 1'})
        comment = Comment.objects.order_by('-date').first()
        self.client.post('/create_comment/', {'obj_type': 'c', 'obj_id': comment.pk, 'text': 'Comment 2'})
        self.client.post('/create_comment/', {'obj_type': 'c', 'obj_id': comment.pk, 'text': 'Comment 3'})
        self.client.post('/create_comment/', {'obj_type': '1', 'obj_id': self.ids[1], 'text': 'Comment 4'})
        comment = Comment.objects.order_by('-date').first()
        self.client.post('/create_comment/', {'obj_type': 'c', 'obj_id': comment.pk, 'text': 'Comment 5'})
        self.client.post('/create_comment/', {'obj_type': 'c', 'obj_id': comment.pk, 'text': 'Comment 6'})
        comment = Comment.objects.order_by('-date').first()
        self.client.post('/create_comment/', {'obj_type': 'c', 'obj_id': comment.pk, 'text': 'Comment 7'})
        comments = Comment.objects.order_by('date')

        res = self.client.post('/get_tree/', {'obj_id': self.ids[0], 'obj_type': '0'})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'application/json')
        content = json.loads(str(res.content, encoding='utf8'))
        self.assertNotIn('error', content)
        comment_tree = json.loads(content['comments'])
        self.assertEqual(comment_tree.get('name'), 'Blog post')
        self.assertIn('comments', comment_tree)
        self.assertEqual(len(comment_tree['comments']), 1)
        self.assertEqual(comment_tree['comments'][0]['text'], 'Comment 1')
        self.assertIn('children', comment_tree['comments'][0])
        self.assertEqual(len(comment_tree['comments'][0]['children']), 2)
        self.assertEqual(comment_tree['comments'][0]['children'][0]['text'], 'Comment 2')
        self.assertEqual(comment_tree['comments'][0]['children'][1]['text'], 'Comment 3')

        res = self.client.post('/get_tree/', {'obj_id': comments[3].pk, 'obj_type': 'c'})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'application/json')
        content = json.loads(str(res.content, encoding='utf8'))
        self.assertNotIn('error', content)
        comment_tree = json.loads(content['comments'])
        self.assertEqual(comment_tree.get('text'), 'Comment 4')
        self.assertIn('children', comment_tree)
        self.assertEqual(len(comment_tree['children']), 2)
        self.assertEqual(comment_tree['children'][0]['text'], 'Comment 5')
        self.assertEqual(comment_tree['children'][1]['text'], 'Comment 6')
        self.assertIn('children', comment_tree['children'][1])
        self.assertEqual(len(comment_tree['children'][1]['children']), 1)
        self.assertEqual(comment_tree['children'][1]['children'][0]['text'], 'Comment 7')

    def test_6_downloads(self):
        # 1[], 2[3, 4], None
        self.client.post('/create_comment/', {'obj_type': '0', 'obj_id': self.ids[0], 'text': 'Comment 1'})
        self.client.post('/create_comment/', {'obj_type': '1', 'obj_id': self.ids[1], 'text': 'Comment 2'})
        comment = Comment.objects.order_by('-date').first()
        self.client.post('/create_comment/', {'obj_type': 'c', 'obj_id': comment.pk, 'text': 'Comment 3'})
        self.client.post('/create_comment/', {'obj_type': 'c', 'obj_id': comment.pk, 'text': 'Comment 4'})
        comments = Comment.objects.order_by('date')
        self.client.post('/change_comment/', {'comment_id': comments[1].pk, 'text': 'New comment 2'})
        self.client.post('/delete_comment/', {'comment_id': comments[3].pk})
        comments = Comment.objects.order_by('date')

        res = self.client.post('/download_history/', {'file_type': 'json', 'target_id': self.author.pk})
        self.assertEqual(res.status_code, 200)
        self.assertNotEqual(res['Content-Type'], 'application/json')

        fp = BytesIO()
        for l in res.streaming_content:
            fp.write(l)
        fp.seek(0)
        content = json.loads(fp.read().decode('utf8'))
        self.assertEqual(len(content), 6)
        for i in range(4):
            self.assertIsNone(content[i]['old_text'])
            self.assertEqual(content[i]['new_text'], 'Comment %s' % (i + 1))
        self.assertEqual(content[4]['old_text'], 'Comment 2')
        self.assertEqual(content[4]['new_text'], 'New comment 2')
        self.assertEqual(content[5]['old_text'], 'Comment 4')
        self.assertIsNone(content[5]['new_text'])

        downloads = DownloadHistory.objects.all()
        self.assertEqual(len(downloads), 1)
        user_download = downloads.first()
        self.assertEqual(user_download.user, self.author)
        self.assertEqual(user_download.target, self.author)
        self.assertEqual(user_download.file_type, '1')
        # TODO: test 'txt' and 'xml' formats


class MyToy:
    def __init__(self):
        self.author, created = User.objects.get_or_create(username='user')
        if created:
            self.author.set_password('passwd')
            self.author.save()
        self.client = Client()
        self.ids = [
            BlogPost.objects.get_or_create(name='Blog post')[0].pk,
            UserPage.objects.get_or_create(name='User page')[0].pk,
            AnotherObject.objects.get_or_create(name='Another object')[0].pk
        ]
        self.__login()

    def __login(self):
        res = self.client.post('/login/', {'username': 'user', 'password': 'passwd'})
        if res.status_code != 200:
            raise ValueError('Login with code %s' % res.status_code)

    def clear_db(self):
        CommentRoot.objects.all().delete()
        CommentHistory.objects.all().delete()

    def create_comment(self, obj_type, obj_id=None):
        if obj_type != 'c':
            obj_id = self.ids[int(obj_type)]
        elif obj_id is None:
            raise ValueError('Please set id')
        res = self.client.post('/create_comment/', {
            'obj_type': obj_type, 'obj_id': obj_id, 'text': 'Comment for %s (%s) [%s]' % (obj_id, obj_type, now())
        })
        if res.status_code != 200:
            raise ValueError('Return status %s' % res.status_code)
        if res['Content-Type'] != 'application/json':
            raise ValueError('Content is not json')
        return json.loads(str(res.content, encoding='utf8'))

    def change_comment(self, comment_id):
        res = self.client.post('/change_comment/', {'comment_id': comment_id, 'text': 'New comment'})
        if res.status_code != 200:
            raise ValueError('Return status %s' % res.status_code)
        if res['Content-Type'] != 'application/json':
            raise ValueError('Content is not json')
        return json.loads(str(res.content, encoding='utf8'))

    def delete_comment(self, comment_id):
        res = self.client.post('/delete_comment/', {'comment_id': comment_id})
        if res.status_code != 200:
            raise ValueError('Return status %s' % res.status_code)
        if res['Content-Type'] != 'application/json':
            raise ValueError('Content is not json')
        return json.loads(str(res.content, encoding='utf8'))

    def first_level_list(self, obj_type, obj_id):
        res = self.client.get('/first_level/1/', {'obj': obj_id, 'type': obj_type})
        if res.status_code != 200:
            raise ValueError('Return status %s' % res.status_code)
        if res['Content-Type'] != 'application/json':
            raise ValueError('Content is not json')
        return json.loads(str(res.content, encoding='utf8'))

    def get_tree(self, obj_type, obj_id):
        res = self.client.post('/get_tree/', {'obj_id': obj_id, 'obj_type': obj_type})
        if res.status_code != 200:
            raise ValueError('Return status %s' % res.status_code)
        if res['Content-Type'] != 'application/json':
            raise ValueError('Content is not json')
        return json.loads(str(res.content, encoding='utf8'))

    def download_history(self, file_type):
        res = self.client.post('/download_history/', {
            'file_type': file_type, 'target_id': self.author.pk,
            # 'date_from': "[2016,11,17,22,41,36]",
            # 'date_to': "[2016,11,17,22,44]"
        })
        if res.status_code != 200:
            raise ValueError('Return status %s' % res.status_code)
        if res['Content-Type'] == 'application/json':
            raise ValueError(json.loads(str(res.content, encoding='utf8'))['error'])
        with open('test.%s' % file_type, mode='wb') as fp:
            for l in res.streaming_content:
                fp.write(l)

    def user_downloads(self):
        res = self.client.post('/user_downloads/', {'user_id': self.author.pk})
        if res.status_code != 200:
            raise ValueError('Return status %s' % res.status_code)
        if res['Content-Type'] != 'application/json':
            raise ValueError('Content is not json')
        return json.loads(str(res.content, encoding='utf8'))
