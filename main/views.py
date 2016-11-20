import mimetypes
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage
from django.http import JsonResponse, StreamingHttpResponse
from Comments.vars import NUM_OF_COMMENTS_ON_PAGE
from main.utils import *


def user_login(request):
    user = authenticate(username=request.POST.get('username'), password=request.POST.get('password'))
    if user is not None and user.is_active:
        login(request, user)
    return JsonResponse({})


@login_required
def create_comment_view(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Wrong reqeust method'})
    if any(x not in request.POST for x in ['obj_type', 'obj_id', 'text']):
        return JsonResponse({'error': 'Wrong list of arguments'})
    try:
        create_comment(request.user, request.POST['obj_type'], request.POST['obj_id'], request.POST['text'])
    except Exception as e:
        return JsonResponse({'error': str(e)})
    return JsonResponse({})


@login_required
def change_comment_view(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Wrong reqeust method'})
    if any(x not in request.POST for x in ['comment_id', 'text']):
        return JsonResponse({'error': 'Wrong list of arguments'})
    try:
        change_comment(request.user, request.POST['comment_id'], request.POST['text'])
    except Exception as e:
        return JsonResponse({'error': str(e)})
    return JsonResponse({})


@login_required
def delete_comment_view(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Wrong reqeust method'})
    if 'comment_id' not in request.POST:
        return JsonResponse({'error': 'Wrong list of arguments'})
    try:
        delete_comment(request.user, request.POST['comment_id'])
    except Exception as e:
        return JsonResponse({'error': str(e)})
    return JsonResponse({})


def first_level_list(request, page):
    if request.method != 'GET':
        return JsonResponse({'error': 'Wrong reqeust method'})
    if any(x not in request.GET for x in ['obj', 'type']):
        return JsonResponse({'error': 'Wrong list of arguments'})
    page = int(page)
    try:
        all_comments = first_level_comments(request.GET['type'], request.GET['obj'])
    except Exception as e:
        return JsonResponse({'error': str(e)})
    p = Paginator(all_comments, NUM_OF_COMMENTS_ON_PAGE)
    try:
        comments = p.page(page)
    except EmptyPage:
        page = p.num_pages
        comments = p.page(p.num_pages)
    # TODO: add authors and dates of comments
    comments = list([page + i, {'text': comments[i].text}] for i in range(len(comments)))
    return JsonResponse({'comments': json.dumps(comments)})


def get_tree(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Wrong reqeust method'})
    if any(x not in request.POST for x in ['obj_type', 'obj_id']):
        return JsonResponse({'error': 'Wrong list of arguments'})
    try:
        comments = CommentTree(request.POST['obj_type'], request.POST['obj_id']).get_tree()
    except Exception as e:
        print(e)
        return JsonResponse({'error': str(e)})
    return JsonResponse({'comments': json.dumps(comments)})


@login_required
def download_history(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Wrong reqeust method'})
    if any(x not in request.POST for x in ['file_type', 'target_id']):
        return JsonResponse({'error': 'Wrong list of arguments'})
    try:
        target = User.objects.get(pk=request.POST['target_id'])
    except ObjectDoesNotExist:
        return JsonResponse({'error': 'The target was not found'})
    try:
        res = DownloadCommentsHistory(
            request.user, target,
            request.POST.get('date_from'),
            request.POST.get('date_to'),
            request.POST['file_type']
        )
    except Exception as e:
        return JsonResponse({'error': str(e)})
    file_name = "history-%s.%s" % (res.target.pk, request.POST['file_type'])
    response = StreamingHttpResponse(IterContent(res.type, res.history), content_type=mimetypes.guess_type(file_name)[0])
    response['Content-Disposition'] = "attachment; filename=%s" % file_name
    return response


@login_required
def user_downloads(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Wrong reqeust method'})
    if 'user_id' not in request.POST:
        return JsonResponse({'error': 'user_id is required in POST params'})
    try:
        author = User.objects.get(pk=request.POST['user_id'])
    except ObjectDoesNotExist:
        return JsonResponse({'error': 'User was not found'})
    return JsonResponse({'data': json.dumps(UserDownloads(author).data)})
