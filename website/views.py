import re
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404, \
    render_to_response
from django.core.context_processors import csrf
from django.template import RequestContext
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Max
from django.core.mail import EmailMultiAlternatives
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.urlresolvers import reverse
from django.contrib.auth import get_user_model
from django.conf import settings
from django.contrib import messages
from django.utils.html import strip_tags

from website.models import Question, Answer, Notification, \
    AnswerComment, FossCategory, Profile, SubFossCategory
from website.forms import NewQuestionForm, AnswerQuestionForm, \
    AnswerCommentForm
from website.helpers import get_video_info, prettify
from django.db.models import Count
from django.core.mail import send_mail
from django.core.mail import EmailMultiAlternatives
from forums.settings import SET_TO_EMAIL_ID

User = get_user_model()

admins = (
   9, 4376, 4915, 14595, 12329, 22467, 5518, 30705
)
categories = FossCategory.objects.order_by('name')
# for home page


def home(request):
    questions = Question.objects.all().order_by('date_created').reverse()[:10]
    context = {
        'categories': categories,
        'questions': questions
    }
    return render(request, "website/templates/index.html", context)


# to get all questions posted till now and pagination, 20 questions at a time
def questions(request):
    questions = Question.objects.all().order_by('date_created').reverse()
    context = {
        'questions': questions,
    }
    return render(request, 'website/templates/questions.html', context)


# get particular question, with votes,anwsers
def get_question(request, question_id=None, pretty_url=None):
    question = get_object_or_404(Question, id=question_id)
    sub_category = True
    if question.sub_category == "" or str(question.sub_category) == 'None':
        sub_category = False
    else:
        sub_category = True
    pretty_title = prettify(question.title)
    if pretty_url != pretty_title:
        return HttpResponseRedirect('/question/' + question_id + '/' +
                                    pretty_title)
    answers = question.answer_set.all()
    ans_count = question.answer_set.count()
    form = AnswerQuestionForm()
    thisuserupvote = question.userUpVotes.filter(id=request.user.id).count()
    thisuserdownvote = question.userDownVotes\
                               .filter(id=request.user.id).count()
    net_count = question.userUpVotes.count() - question.userDownVotes.count()

    ans_votes = []

    for vote in answers:
        net_ans_count = vote.userUpVotes.count() - vote.userDownVotes.count()
        ans_votes.append([vote.userUpVotes.filter(id=request.user.id).count(),
                          vote.userDownVotes.filter(id=request.user.id).count(),
                          net_ans_count])

    main_list = zip(answers, ans_votes)
    context = {
        'ans_count': ans_count,
        'question': question,
        'sub_category': sub_category,
        'main_list': main_list,
        'form': form,
        'thisUserUpvote': thisuserupvote,
        'thisUserDownvote': thisuserdownvote,
        'net_count': net_count,
        'num_votes': question.num_votes,
        'ans_votes': ans_votes,

    }
    context.update(csrf(request))
    # updating views count
    question.views += 1
    question.save()

    return render(request, 'website/templates/get-question.html', context)


@login_required
def question_answer(request, qid):
    """post answer to a question

    end notification to the user, whose question is answered
    if anwser is posted by the owner of the question, no notification is sent
    """

    context = {}
    question = get_object_or_404(Question, id=qid)

    if request.method == 'POST':
        form = AnswerQuestionForm(request.POST)
        answers = question.answer_set.all()
        answer = Answer()

        answer.uid = request.user.id
        if form.is_valid():
            cleaned_data = form.cleaned_data
            qid = cleaned_data['question']
            body = str(cleaned_data['body'])
            answer.body = body.splitlines()
            answer.question = question
            answer.body = body.encode('unicode_internal')
            answer.save()
            if question.user_id != request.user.id:
                notification = Notification()
                notification.uid = question.user_id
                notification.pid = request.user.id
                notification.qid = qid
                notification.aid = answer.id
                notification.save()
                user = User.objects.get(id=question.user_id)

            # Sending email when a new question is asked
            sender_name = "FOSSEE Forums"
            sender_email = "forums@fossee.in"
            subject = "FOSSEE Forums - {0} - Your question has been answered"\
                      .format(question.category)
            to = [question.user.email, 'forum-notifications@fossee.in', ]
            url = settings.EMAIL_URL
            message = "  "
            message = """ The following new question has been posted in
                         the FOSSEE Forum: \n\n
                         Title: {0} \n
                         Category: {1}\n
                         Link: {2}\n\n
                         Regards,\nFOSSEE Team,\nIIT Bombay.
                         """.format(
                question.title,
                question.category,
                'http://forums.fossee.in/question/' + str(question.id) +
                "#answer" + str(answer.id)
            )

            send_mail(subject, message, sender_email, to)
            return HttpResponseRedirect("/question/" + str(question.id))
        else:
            context['form'] = form
            context['question'] = question

    else:
        category = request.GET.get('category')
        form = NewQuestionForm(category=category)
        context['category'] = category
        context['question'] = question

    context['form'] = form
   
    context.update(csrf(request))
    return render(request, 'website/templates/get-question.html', context)


@login_required
def answer_comment(request):
    """comments for specific answer

    notification is sent to owner of the answer notify other users in the comment thread
    """
    context = {}

    if request.method == 'POST':
        answer_id = request.POST['answer_id']
        answer = Answer.objects.get(pk=answer_id)
        answers = answer.question.answer_set.all()
        answer_creator = answer.user()
        form = AnswerCommentForm(request.POST)
        if form.is_valid():
            body = request.POST['body']
            body = str(body)

            comment = AnswerComment()
            comment.uid = request.user.id
            comment.answer = answer
            comment.body = body.encode('unicode_internal')

            comment.save()
            # notifying the answer owner

            if answer.uid != request.user.id:
                notification = Notification()
                notification.uid = answer.uid
                notification.pid = request.user.id
                notification.qid = answer.question.id
                notification.aid = answer.id
                notification.cid = comment.id
                notification.save()

                user = User.objects.get(id=answer.uid)
            try:
                sender_name = "FOSSEE Forums"
                sender_email = "forums@fossee.in"
                subject = "FOSSEE Forums - {0} - Comment for your answer"\
                          .format(answer.question.category)
                to = [answer_creator.email, 'forum-notifications@fossee.in', ]
                url = settings.EMAIL_URL
                message = """
                    A comment has been posted on your answer. \n\n
                    Title: {0}\n
                    Category: {1}\n
                    Link: {2}\n\n
                    Regards,\nFOSSEE Team,\nIIT Bombay.
                    """.format(
                    answer.question.title,
                    answer.question.category,
                    'http://forums.fossee.in/question/' + str(answer.question.id) +
                    "#answer" + str(answer.id)
                    )
                send_mail(subject, message, sender_email, to)
                # notifying other users in the comment thread
                uids = answer.answercomment_set\
                             .filter(answer=answer).values_list('uid', flat=True)
                answer_comments = answer.answercomment_set.filter(answer=answer)
                comment_creator_emails = []
                for c in answer_comments:
                    comment_creator = c.user()
                    email = comment_creator.email
                    comment_creator_emails.append(email)
                    comment_creator_emails.append('forum-notifications@fossee.in')
                # getting distinct uids
                uids = set(uids)
                uids.remove(request.user.id)
                for uid in uids:
                    notification = Notification()
                    notification.uid = uid
                    notification.pid = request.user.id
                    notification.qid = answer.question.id
                    notification.aid = answer.id
                    notification.cid = comment.id
                    notification.save()

                    user = User.objects.get(id=uid)
                sender_name = "FOSSEE Forums"
                sender_email = "forums@fossee.in"
                subject = "FOSSEE Forums - {0} - Comment has a reply"\
                          .format(answer.question.category)
                to = comment_creator_emails
                url = settings.EMAIL_URL
                message = """
                    A reply has been posted on your comment.\n\n
                    Title: {0}\n
                    Category: {1}\n
                    Link: {2}\n\n
                    Regards,\nFOSSEE Team,\nIIT Bombay.
                    """.format(
                    answer.question.title,
                    answer.question.category,
                    'http://forums.fossee.in/question/' +
                    str(answer.question.id) + "#answer" + str(answer.id)
                )

                send_mail(subject, message, sender_email, to)
            except:
                pass
            return HttpResponseRedirect("/question/" + str(answer.question.id))

        else:

            context.update(
                {'form': form,
                 'question': answer.question,
                 'answers': answers})
            return render(request, 'website/templates/get-question.html',
                          context)
    context.update(csrf(request))
    context.update(
      {'form': form,
       'question': answer.question,
       'answers': answers})

    return render(request, 'website/templates/get-question.html', context)


def filter(request,  category=None, tutorial=None, minute_range=None,
           second_range=None):
    dict_context = {}
    context = {
        'category': category,
        'tutorial': tutorial,
        'minute_range': minute_range,
        'second_range': second_range
    }
    if category and tutorial and minute_range and second_range:
        questions = Question.objects\
                            .filter(category=category)\
                            .filter(tutorial=tutorial)\
                            .filter(minute_range=minute_range)\
                            .filter(second_range=second_range)\
                            .order_by('date_created').reverse()
    elif tutorial is None:
        questions = Question.objects\
                            .filter(category__name=category)\
                            .order_by('date_created').reverse()
    elif minute_range is None:
        questions = Question.objects\
                            .filter(category__name=category)\
                            .filter(sub_category=tutorial)\
                            .order_by('date_created').reverse()
    else:
        questions = Question.objects\
                            .filter(category=category)\
                            .filter(sub_category=tutorial)\
                            .filter(minute_range=minute_range)\
                            .order_by('date_created').reverse()

    if 'qid' in request.GET:
        context['qid'] = int(request.GET['qid'])
     
    categories = FossCategory.objects.filter(name=category)
    sub_category = SubFossCategory.objects.filter(name=tutorial)
    try:
        name = SubFossCategory.objects.get(name=tutorial)
        dict_context['name'] = name
    except:
        pass        
    dict_context = {
            'questions': questions,
            'categories': categories,
            'tutorial': sub_category,
           }
        
    return render(request, 'website/templates/filter.html', dict_context)


def tags(request, tag=None):
    """filter the questions according to their tags"""

    tag_s = str(tag)    # converting tag from unicode to string type
    context = {}

    questions = Question.objects.filter(tags__name__in=[tag_s])

    context = {'questions': questions,
               'tag': tag_s
               }
    return render(request, 'website/templates/filter_tags.html', context)


@login_required
def new_question(request):
    """post a new question on to forums

    notification is sent to mailing list team@fossee.in
    """
    context = {}
    toolbox = False
    user = request.user
    all_category = FossCategory.objects.all()
    if request.method == 'POST':
        form = NewQuestionForm(request.POST)
        if form.is_valid():

            cleaned_data = form.cleaned_data
            # for referencing foreign key and taggit-tables
            question = Question.objects.create(title=cleaned_data['title'],
                                               user=request.user,
                                               category=cleaned_data['category'],
                                               )

            question.sub_category = cleaned_data['tutorial']
            if (question.sub_category == "Select a Sub Category"):
                if str(question.category) == "Scilab Toolbox":
                    context.update(csrf(request))
                    category = request.POST.get('category', None)
                    tutorial = request.POST.get('tutorial', None)
                    context['category'] = category
                    context['tutorial'] = tutorial
                    context['form'] = form
                    context['toolbox'] = toolbox
                    return render(request,
                                  'website/templates/new-question.html',
                                  context)
                else:
                    pass
                question.sub_category = ""
                question.save()

            question.body = cleaned_data['body']

            dummy_tag = cleaned_data['tag']

            for t in dummy_tag:
                question.tags.add(t)
            body = strip_tags(question.body)
            question.views = 1

            question.save()
            if str(question.sub_category) == 'None':
                question.sub_category = ""
                question.save()
            # Sending email when a new question is asked
            try:
                sender_name = "FOSSEE Forums"
                sender_email = "forums@fossee.in"
                subject = "FOSSEE Forums - {0} - New Question"\
                          .format(question.category)
                to = (question.category.email, 'forum-notifications@fossee.in')
                url = settings.EMAIL_URL

                message = """
                    The following new question has been posted in the FOSSEE Forum: <br>
                    <b> Title: </b>{0}<br>
                    <b> Category: </b>{1}<br>
                    <b> Link: </b><a href="{3}">{3}</a><br>
                    <b> Question : </b>{2}<br>
                """.format(
                    question.title,
                    question.category,
                    question.body,
                    'http://forums.fossee.in/question/'+str(question.id),
                )
                email = EmailMultiAlternatives(
                    subject, '',
                    sender_email, to,
                    headers={"Content-type": "text/html;charset=iso-8859-1"}
                )
                email.attach_alternative(message, "text/html")
                email.send(fail_silently=True)
            except:
                pass
            return HttpResponseRedirect('/')
        else:
            context.update(csrf(request))
            category = request.POST.get('category', None)
            tutorial = request.POST.get('tutorial', None)
            context['category'] = category
            context['tutorial'] = tutorial
            context['form'] = form
            context['toolbox'] = toolbox
            if category:
                context['FossCategory'] = FossCategory.objects.get(id=category)

            return render(request, 'website/templates/new-question.html',
                          context)
    else:

        category = request.GET.get('category')
        if category == 12:
            toolbox = True
        tutorial = request.GET.get('tutorial')
        form = NewQuestionForm(category=category, tutorial=tutorial)
        context['category'] = category
        context['tutorial'] = tutorial
        context['toolbox'] = toolbox
        if category:
            context['FossCategory'] = FossCategory.objects.get(id=category)
    context['form'] = form   
    context.update(csrf(request))
    return render(request, 'website/templates/new-question.html', context)


def vote_post(request):
    """return number of votes and initial votes

    user who asked the question,cannot vote his/or anwser
    other users can post votes
    """
    post_id = int(request.POST.get('id'))

    vote_type = request.POST.get('type')
    vote_action = request.POST.get('action')
    question_id = request.POST.get('id')
    question = get_object_or_404(Question, id=question_id)
    cur_post = get_object_or_404(Question, id=post_id)
    thisuserupvote = cur_post.userUpVotes.filter(id=request.user.id).count()
    thisuserdownvote = cur_post.userDownVotes\
                               .filter(id=request.user.id).count()
    initial_votes = cur_post.userUpVotes.count() - cur_post\
                            .userDownVotes.count()
    if request.user.id != question.user_id:

        if vote_action == 'vote':
            if (thisuserupvote == 0) and (thisuserdownvote == 0):
                if vote_type == 'up':
                    cur_post.userUpVotes.add(request.user)
                elif vote_type == 'down':
                    cur_post.userDownVotes.add(request.user)
                else:
                    return HttpResponse("Error: Unknown vote-type passed.")
            elif (thisuserupvote == 1) and (thisuserdownvote == 0):
                if vote_type == 'down':
                    cur_post.userUpVotes.remove(request.user)
                    cur_post.userDownVotes.add(request.user)
            elif (thisuserupvote == 0) and (thisuserdownvote == 1):
                if vote_type == 'up':
                    cur_post.userDownVotes.remove(request.user)
                    cur_post.userUpVotes.add(request.user)
            else:
                return HttpResponse(initial_votes)
                # This loop is for canceling vote
        elif vote_action == 'recall-vote':
            if (vote_type == 'up') and (thisuserupvote == 1):
                cur_post.userUpVotes.remove(request.user)
            elif (vote_type == 'down') and (thisuserdownvote == 1):
                cur_post.userDownVotes.remove(request.user)
            else:
                # "Error - Unknown vote type or no vote to recall"
                return HttpResponse(initial_votes)
        else:
            return HttpResponse("Error: Bad Action.")

        num_votes = cur_post.userUpVotes.count() - cur_post.userDownVotes\
                                                           .count()
        cur_post.num_votes = num_votes
        cur_post.save()
        return HttpResponse(num_votes)
            
    else:
        return HttpResponse(initial_votes)


def ans_vote_post(request):
    """return number of votes and initial votes

    user who posted the answer, cannot vote his/or anwser,
    other users can post votes
    """
    post_id = int(request.POST.get('id'))
    vote_type = request.POST.get('type')
    vote_action = request.POST.get('action')
    answer_id = request.POST.get('id')

    answer = Answer.objects.get(pk=answer_id)
    cur_post = get_object_or_404(Answer, id=post_id)

    userupvote = cur_post.userUpVotes.filter(id=request.user.id).count()
    userdownvote = cur_post.userDownVotes.filter(id=request.user.id).count()

    initial_votes = cur_post.userUpVotes.count() - cur_post.userDownVotes\
                                                           .count()

    if request.user.id != answer.uid:

        # This loop is for voting
        if vote_action == 'vote':
            if (userupvote == 0) and (userdownvote == 0):
                if vote_type == 'up':
                    cur_post.userUpVotes.add(request.user)
                elif vote_type == 'down':
                    cur_post.userDownVotes.add(request.user)
                else:
                    return HttpResponse("Error: Unknown vote-type passed.")
            elif (userupvote == 1) and (userdownvote == 0):
                if vote_type == 'down':
                    cur_post.userUpVotes.remove(request.user)
                    cur_post.userDownVotes.add(request.user)
            elif (userupvote == 0) and (userdownvote == 1):
                if vote_type == 'up':
                    cur_post.userDownVotes.remove(request.user)
                    cur_post.userUpVotes.add(request.user)
            else:
                return HttpResponse(initial_votes)
        # This loop is for canceling vote
        elif vote_action == 'recall-vote':
            if (vote_type == 'up') and (userupvote == 1):
                cur_post.userUpVotes.remove(request.user)
            elif (vote_type == 'down') and (userdownvote == 1):
                cur_post.userDownVotes.remove(request.user)
            else:
                # "Error - Unknown vote type or no vote to recall
                return HttpResponse(initial_votes)
        else:
            return HttpResponse("Error: Bad Action.")

        num_votes = cur_post.userUpVotes.count() - cur_post.userDownVotes\
                                                           .count()
        cur_post.num_votes = num_votes
        cur_post.save()
       
        return HttpResponse(num_votes)
    else:
        return HttpResponse(initial_votes)


@login_required
def user_questions(request, user_id):
    """ Notification Section

    It is used to get all questions of a specific users
    """
    marker = 0
    if 'marker' in request.GET:
        marker = int(request.GET['marker'])

    if str(user_id) == str(request.user.id):
        total = Question.objects.filter(user_id=user_id).count()
        total = int(total - (total % 10 - 10))
        questions = Question.objects\
                            .filter(user_id=user_id)\
                            .order_by('date_created')\
                            .reverse()[marker:marker+10]

        context = {
            'questions': questions,
            'total': total,
            'marker': marker
        }
       
        return render(request, 'website/templates/user-questions.html',
                      context)
    return HttpResponse("go away")


# to get all answers of a specific users
@login_required
def user_answers(request, user_id):
    marker = 0
    if 'marker' in request.GET:
        marker = int(request.GET['marker'])

    if str(user_id) == str(request.user.id):
        total = Answer.objects.filter(uid=user_id).count()
        total = int(total - (total % 10 - 10))
        answers = Answer.objects\
                        .filter(uid=user_id)\
                        .order_by('date_created')\
                        .reverse()[marker:marker+10]
        context = {
            'answers': answers,
            'total': total,
            'marker': marker
        }
        return render(request, 'website/templates/user-answers.html', context)
    return HttpResponse("go away")


# notification if any on header, when user logs in to the account
@login_required
def user_notifications(request, user_id):
    if str(user_id) == str(request.user.id):
        try:
            notifications = Notification\
                            .objects.filter(uid=user_id)\
                                    .order_by('date_created').reverse()
            context = {
                'notifications': notifications
            }
            return render(request, 'website/templates/notifications.html',
                          context)
        except:
            Notification.objects.filter(uid=request.user.id).delete()
            return HttpResponseRedirect("/user/{0}/notifications/"
                                        .format(request.user.id))


# to clear notification from header, once viewed or cancelled
@login_required
def clear_notifications(request):
    Notification.objects.filter(uid=request.user.id).delete()
    return HttpResponseRedirect("/user/{0}/notifications/"
                                .format(request.user.id))


def search(request):
    context = {
        'categories': categories
    }
    return render(request, 'website/templates/search.html', context)


# Ajax Section
# All the ajax views go below
@csrf_exempt
def ajax_category(request):
    context = {
        'categories': categories
    }
    return render(request, 'website/templates/ajax_tutorials.html', context)


@csrf_exempt
def ajax_tutorials(request):
    if request.method == 'POST':
        category = request.POST.get('category')
        if category == '12':
            tutorials = SubFossCategory.objects.filter(parent_id=category)
            context = {
                'tutorials': tutorials
            }
            return render(request, 'website/templates/ajax-tutorials.html',
                          context)
        else:
            return HttpResponse("changed")
            pass


@csrf_exempt
def ajax_duration(request):
    if request.method == 'POST':
        category = request.POST['category']
        tutorial = request.POST['tutorial']
        video_detail = SubFossCategory.objects.filter(parent_id=category)
        # convert minutes to 1 if less than 0
        # convert seconds to nearest upper 10th number eg(23->30)
        return render(request, 'website/templates/ajax-duration.html')


@csrf_exempt
def ajax_question_update(request):
    if request.method == 'POST':
        qid = request.POST['question_id']
        title = request.POST['question_title']
        body = request.POST['question_body']
        question = get_object_or_404(Question, pk=qid)
        if question:
            if question.user.id == request.user.id or\
               request.user.id in admins:
                question.title = title
                question.body = body.encode('unicode_escape')
                question.save()
        return HttpResponse("saved")


@csrf_exempt
def ajax_details_update(request):
    if request.method == 'POST':
        qid = request.POST['qid']
        category = request.POST['category']
        tutorial = request.POST['tutorial']
        minute_range = request.POST['minute_range']
        second_range = request.POST['second_range']
        question = get_object_or_404(Question, pk=qid)
        if question:
            if question.uid == request.user.id or request.user.id in admins:
                question.category = category
                question.tutorial = tutorial
                question.minute_range = minute_range
                question.second_range = second_range
                question.save()
            return HttpResponse("saved")


@csrf_exempt
def ajax_answer_update(request):
    if request.method == 'POST':
        aid = request.POST['answer_id']
        body = request.POST['answer_body']
        answer = get_object_or_404(Answer, pk=aid)
        if answer:
            if answer.uid == request.user.id or request.user.id in admins:
                answer.body = body.encode('unicode_escape')
                answer.save()
        return HttpResponse("saved")


@csrf_exempt
def ajax_answer_comment_update(request):
    if request.method == "POST":
        comment_id = request.POST["comment_id"]
        comment_body = request.POST["comment_body"]
        comment = get_object_or_404(AnswerComment, pk=comment_id)
        if comment:
            if comment.uid == request.user.id or request.user.id in admins:
                comment.body = comment_body.encode('unicode_escape')
                comment.save()
        return HttpResponse("saved")


@csrf_exempt
def ajax_similar_questions(request):
    if request.method == 'POST':
        category = request.POST['category']
        tutorial = request.POST['tutorial']
        minute_range = request.POST['minute_range']
        second_range = request.POST['second_range']

        # add more filtering when the forum grows
        questions = Question.objects.filter(category=category)\
                            .filter(tutorial=tutorial)
        context = {
            'questions': questions
        }
        return render(request, 'website/templates/ajax-similar-questions.html',
                      context)


@csrf_exempt
def ajax_notification_remove(request):
    if request.method == "POST":
        nid = request.POST["notification_id"]
        notification = Notification.objects.get(pk=nid)
        if notification:
            if notification.uid == request.user.id:
                notification.delete()
                return HttpResponse("removed")
    return HttpResponse("failed")


@csrf_exempt
def ajax_keyword_search(request):
    if request.method == "POST":
        key = request.POST['key']

        questions = Question.objects.filter(title__contains=key)

        context = {
            'questions': questions
        }
        return render(request, 'website/templates/ajax-keyword-search.html',
                      context)


@csrf_exempt
def ajax_time_search(request):
    if request.method == "POST":
        category = request.POST.get('category')
        tutorial = request.POST.get('tutorial')
        minute_range = request.POST.get('minute_range')
        second_range = request.POST.get('second_range')
        questions = None
        if category:
            questions = Question\
                        .objects.filter(category=category.replace(' ', '-'))
        if tutorial:
            questions = questions.filter(tutorial=tutorial.replace(' ', '-'))
        if minute_range:
            questions = questions.filter(category=category.replace(' ', '-'),
                                         tutorial=tutorial.replace(' ', '-'),
                                         minute_range=minute_range)
        if second_range:
            questions = questions.filter(category=category.replace(' ', '-'),
                                         tutorial=tutorial.replace(' ', '-'),
                                         second_range=second_range)
        context = {
            'questions': questions
        }
        return render(request, 'website/templates/ajax-time-search.html',
                      context)


@csrf_exempt
def category_tags(request):
    category = request.GET.get("category")
    FossCategory_selected = FossCategory.objects.get(id=category)
    list_of_tags = ''
    for t in FossCategory_selected.default_tags.all():
        list_of_tags = str(t) + ' ' + list_of_tags

    return HttpResponse(list_of_tags)


@csrf_exempt
def ajax_vote(request):
    # for future use
    pass
