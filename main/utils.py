import json
from django.core.exceptions import ObjectDoesNotExist
from django.utils.timezone import now, datetime, pytz
from main.models import *

COMMENT_TABLES = {
    '0': BlogPost,
    '1': UserPage,
    '2': AnotherObject
}


def get_date_list(date):
    if date is None:
        return None
    date = date.astimezone(pytz.timezone('Europe/Moscow'))
    return [date.year, date.month, date.day, date.hour, date.minute, date.second, date.microsecond]


def get_date_obj(date_list):
    moscow_tz = pytz.timezone('Europe/Moscow')
    return moscow_tz.localize(datetime(*date_list))


def create_comment(author, obj_type, obj_id, text):
    try:
        obj_id = int(obj_id)
    except ValueError:
        raise ValueError('Wrong parent object id')
    if obj_type in list(x[0] for x in OBJECT_TYPES):
        try:
            COMMENT_TABLES[obj_type].objects.get(pk=obj_id)
        except ObjectDoesNotExist:
            raise ValueError('The parent object was not found')
        root = CommentRoot.objects.create(obj_type=obj_type, obj_id=obj_id)
        comment = Comment.objects.create(root=root, author=author, text=text)
        CommentHistory.objects.create(comment=comment, author=comment.author, new_text=comment.text, date=comment.date)
    elif obj_type == 'c':
        try:
            parent_comment = Comment.objects.get(pk=obj_id)
        except ObjectDoesNotExist:
            raise ValueError('The parent comment was not found')
        comment = Comment.objects.create(root=parent_comment.root, author=author, parent=parent_comment, text=text)
        CommentHistory.objects.create(comment=comment, author=comment.author, new_text=comment.text, date=comment.date)
    else:
        raise ValueError('Unsupported comment type')


def change_comment(author, comment_id, text):
    try:
        comment = Comment.objects.get(pk=int(comment_id))
    except ObjectDoesNotExist:
        raise ValueError('The comment was not found')
    except ValueError:
        raise ValueError('Wrong parent object id')
    if comment.text != text:
        old_text = comment.text
        comment.text = text
        comment.save()
        # Update 'comment' so it has correct last_change date
        comment = Comment.objects.get(pk=comment.pk)
        CommentHistory.objects.create(
            comment=comment, author=author, old_text=old_text, new_text=comment.text, date=comment.last_change
        )


def delete_comment(author, comment_id):
    try:
        comment = Comment.objects.get(pk=int(comment_id))
    except ObjectDoesNotExist:
        raise ValueError('The comment was not found')
    except ValueError:
        raise ValueError('Wrong parent object id')
    if len(comment.children.all()) > 0:
        raise ValueError("You can't delete comments with children")
    old_text = comment.text
    comment.delete()
    CommentHistory.objects.create(author=author, old_text=old_text, date=now())


def first_level_comments(obj_type, obj_id):
    try:
        obj_id = int(obj_id)
    except ValueError:
        raise ValueError('Wrong parent object id')
    if obj_type in list(x[0] for x in OBJECT_TYPES):
        try:
            COMMENT_TABLES[obj_type].objects.get(pk=obj_id)
        except ObjectDoesNotExist:
            raise ValueError('The parent object was not found')
        return Comment.objects.filter(parent=None, root__obj_id=obj_id, root__obj_type=obj_type).order_by('date')
    elif obj_type == 'c':
        try:
            Comment.objects.get(pk=obj_id)
        except ObjectDoesNotExist:
            raise ValueError('The parent comment was not found')
        return Comment.objects.filter(parent_id=obj_id)
    else:
        raise ValueError('Unsupported root type')


class CommentTree:
    def __init__(self, obj_type, obj_id):
        self.obj_id = int(obj_id)
        self.type = obj_type
        self.comments_data = {}
        self.hierarchy = {}
        self.__get_comments()

    def __get_comments(self):
        if self.type in list(x[0] for x in OBJECT_TYPES):
            try:
                COMMENT_TABLES[self.type].objects.get(pk=self.obj_id)
            except ObjectDoesNotExist:
                raise ValueError('The parent object was not found')
            comments = Comment.objects.filter(root__obj_id=self.obj_id, root__obj_type=self.type).order_by('date')
        elif self.type == 'c':
            try:
                self.comments_data[self.obj_id] = Comment.objects.get(pk=self.obj_id)
            except ObjectDoesNotExist:
                raise ValueError('The parent comment was not found')
            comments = Comment.objects.filter(
                root__obj_id=self.comments_data[self.obj_id].root.obj_id,
                root__obj_type=self.comments_data[self.obj_id].root.obj_type
            ).order_by('date')
        else:
            raise ValueError('Unsupported root type')
        for comment in comments:
            self.comments_data[comment.pk] = comment
            if comment.parent_id not in self.hierarchy:
                self.hierarchy[comment.parent_id] = []
            self.hierarchy[comment.parent_id].append(int(comment.pk))

    def get_tree(self):
        if self.type != 'c':
            # TODO: only objects with 'name' in table are supported
            return {
                'name': COMMENT_TABLES[self.type].objects.get(pk=self.obj_id).name,
                'obj_type': OBJECT_TYPES[int(self.type)][1],
                'comments': self.__get_children(None)
            }
        return {
            'text': self.comments_data[self.obj_id].text,
            'date': get_date_list(self.comments_data[self.obj_id].date),
            'last_change': get_date_list(self.comments_data[self.obj_id].last_change),
            'children': self.__get_children(self.obj_id),
        }

    def __get_children(self, p_id):
        children = []
        if p_id not in self.hierarchy:
            return []
        for c_id in self.hierarchy[p_id]:
            children.append({
                'text': self.comments_data[c_id].text,
                'date': get_date_list(self.comments_data[c_id].date),
                'last_change': get_date_list(self.comments_data[c_id].last_change),
                'children': self.__get_children(c_id),
            })
        return children


class DownloadCommentsHistory:
    def __init__(self, user, target, from_date, to_date, file_type):
        self.user = user
        self.target = target
        if from_date is not None:
            self.from_date = get_date_obj(json.loads(from_date))
        else:
            self.from_date = None
        if to_date is not None:
            self.to_date = get_date_obj(json.loads(to_date))
        else:
            self.to_date = None
        self.type = None
        for x in COMMENT_HISTORY_TYPE:
            if x[1] == file_type:
                self.type = x[0]
        if self.type is None:
            raise ValueError('Wrong type')
        self.history = self.__get_history()
        self.__save_download()

    def __get_history(self):
        if self.from_date is None and self.to_date is None:
            return CommentHistory.objects.filter(author=self.target).order_by('date')
        elif self.from_date is not None and self.to_date is None:
            return CommentHistory.objects.filter(author=self.target, date__gte=self.from_date).order_by('date')
        elif self.from_date is None and self.to_date is not None:
            return CommentHistory.objects.filter(author=self.target, date__lte=self.from_date).order_by('date')
        return CommentHistory.objects.filter(
            author=self.target, date__range=(self.from_date, self.to_date)
        ).order_by('date')

    def __save_download(self):
        dh_from = self.from_date
        dh_to = self.to_date
        if dh_from is None:
            moscow_tz = pytz.timezone('Europe/Moscow')
            dh_from = moscow_tz.localize(datetime(2016, 11, 20, 16))
        if dh_to is None:
            dh_to = now()
        DownloadHistory.objects.create(
            user=self.user, target=self.target, min_date=dh_from, max_date=dh_to, file_type=self.type
        )


class IterContent:
    def __init__(self, ftype, history):
        self.type = ftype
        self.history = history
        self.need_comma = False
        self.separator = '=' * 50 + '\n'
        self.xml_pref = ' ' * 2

    def __iter__(self):
        yield self.__prefix()
        for ch in self.history:
            if self.type == '0':
                yield self.__txt_block(ch)
            elif self.type == '1':
                yield self.__json_block(ch)
            elif self.type == '2':
                yield self.__xml_block(ch)
        yield self.__postfix()

    def __prefix(self):
        if self.type == '0':
            return self.separator
        elif self.type == '1':
            return '[\n'
        elif self.type == '2':
            return '<?xml version="1.0" encoding="UTF-8" ?>\n<history>'

    def __txt_block(self, comment_change):
        ch_date = comment_change.date.astimezone(pytz.timezone('Europe/Moscow'))
        if comment_change.old_text is None:
            change_block = 'TYPE: <CREATION>\n%s\nTEXT:\n%s\n' % (ch_date, comment_change.new_text)
        elif comment_change.new_text is None:
            change_block = 'TYPE: <DELETION>\n%s\nTEXT:\n%s\n' % (ch_date, comment_change.old_text)
        else:
            change_block = 'TYPE: <EDITION>\n%s\nOLD TEXT:\n%s\nNEW TEXT:\n%s\n' % (
                ch_date, comment_change.old_text, comment_change.new_text
            )
        change_block += self.separator
        return change_block

    def __json_block(self, comment_change):
        data_str = json.dumps({
            'date': str(comment_change.date.astimezone(pytz.timezone('Europe/Moscow'))),
            'old_text': comment_change.old_text, 'new_text': comment_change.new_text
        }, indent=2)
        if self.need_comma:
            data_str = ',\n' + data_str
        else:
            self.need_comma = True
        return data_str

    def __xml_block(self, comment_change):
        xml_block_data = ['<date>%s</date>' % str(comment_change.date.astimezone(pytz.timezone('Europe/Moscow')))]
        if comment_change.old_text is None:
            xml_block_data.append('<type>CREATION</type>')
            xml_block_data.append('<comment>%s</comment>' % comment_change.new_text)
        elif comment_change.new_text is None:
            xml_block_data.append('<type>DELETION</type>')
            xml_block_data.append('<comment>%s</comment>' % comment_change.old_text)
        else:
            xml_block_data.append('<type>EDITION</type>')
            xml_block_data.append('<old>%s</old>' % comment_change.old_text)
            xml_block_data.append('<new>%s</new>' % comment_change.new_text)
        return '\n' + self.xml_pref + '<change>\n' \
               + '\n'.join(list((self.xml_pref * 2 + x) for x in xml_block_data)) \
               + '\n' + self.xml_pref + '</change>'

    def __postfix(self):
        if self.type == '0':
            return '\n'
        elif self.type == '1':
            return '\n]'
        elif self.type == '2':
            return '\n</history>'


class UserDownloads:
    def __init__(self, author):
        self.author = author
        self.data = []
        self.__get_data()

    def __get_data(self):
        for dh in DownloadHistory.objects.filter(user=self.author).order_by('date'):
            self.data.append({
                'target': [dh.target_id, dh.target.username],
                'date': get_date_list(dh.date),
                'date_from': get_date_list(dh.min_date),
                'date_to': get_date_list(dh.max_date),
                'file_type': dh.get_file_type_display()
            })
