
import json
from datetime import datetime
from datetime import timedelta
from pytz import timezone, utc
from flask import (
    abort,
    Blueprint,
    current_app as app,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    Response,
    url_for
)
from flask_login import current_user, login_required
from flask_mongoengine.wtf import model_form
from mongoengine.context_managers import no_dereference
from emojipy import Emoji

from .forms import (
    AnswerForm,
    ActivateForm,
    BulletinAddForm,
    OrderChangeForm,
    TextForm,
    PollForm,
    UploadMediaForm,
    AccountStatsDetailForm,
    ChatUserAttributeAddForm,
    AccountStatsDetailForm,
    QuestionForm
)
from wtforms.widgets import Input

from .helpers import (
    S3Service, validate_fragments_order, datetimeformat,
    stats_to_dicts, group_anwers, get_media_fragment_type)

from .models import (
    Bulletin, Fragment, Story, ChatUser, PollQuestions,
    AccountStats, ChatUserAttribute, ChatUserAnswer,
    ProfileStory, ProfileStoryFragment)

bp = Blueprint('index', __name__)


@bp.route('/')
def index():
    if current_user.is_authenticated and g.current_account:
        return redirect(url_for('.bulletins_list'))

    return render_template('index.html')


@bp.route('/chatusers')
@login_required
def chatusers_list():
    chatusers = ChatUser.objects.no_dereference().filter(account_id=g.current_account)
    return render_template(
        'chatusers/list.html',
        chatusers=chatusers)


@bp.route('/chatusers_ajax')
@login_required
def chatusers_ajax():

    if request.is_xhr:
        chatusers = ChatUser.objects.no_dereference().filter(account_id=g.current_account)

        data = [
            [user.chat_id, user.name, len(user.read_bulletins), datetimeformat(user.last_message), user.disabled, '']
            for user in chatusers
        ]

        return jsonify({'data': data})

    return render_template('chatusers/list_ajax.html')


@bp.route('/chatusers/<string:chat_id>/answers', methods=['GET'])
@login_required
def chatusers_answers_list(chat_id):
    answers = ChatUser.objects.only('question_answers').\
        get_or_404(chat_id=chat_id).question_answers

    if answers is None:
        answers = []

    return render_template(
        'chatusers/answers_list.html',
        answers=answers
    )


@bp.route('/analytics')
@login_required
def analytics():
    sort = request.args.get('s', 'r')
    date_from = request.args.get('f', False)
    date_to = request.args.get('t', False)

    t = timezone(g.current_account.timezone)

    print(sort)
    buletins = g.current_account.bulletins
    stories = []

    for buletin in buletins:
        for content in buletin.content:
            if date_from and buletin.publish_at < datetime.strptime(date_from, '%m/%d/%Y'):
                continue
            if date_to and buletin.publish_at > datetime.strptime(date_to, '%m/%d/%Y'):
                continue

            s = {}
            s['id'] = content.id
            s['title'] = content.title
            s['publish_at'] = utc.localize(buletin.publish_at).astimezone(t)
            #print(content.content)
            with no_dereference(Story):
                s['readers'] = len(content.readers)
            s['readers_by_fragment'] = []
            #f_p = 1
            #s_content = sorted(content.content, key=lambda x: x.order)
            #for f in s_content:
            #    if f.type != Fragment.TYPE_ANSWER:
            #        s['readers_by_fragment'].append({'id':f_p, 'num_readers':f.num_readers})
            #        f_p += 1
            stories.append(s)

        if sort == 'r':
            stories.sort(key=lambda x: x['readers'], reverse=True)
        else:
            stories.sort(key=lambda x: x['publish_at'], reverse=True)

    return render_template('analytics/index.html',
                           stories=stories,
                           sort=sort,
                           date_from=date_from,
                           date_to=date_to)


@bp.route('/analytics/<story_id>')
@login_required
def analytics_story(story_id):

    s = Story.objects.get_or_404(id=story_id)
    story_fragments = set([f.id for f in s.content])

    chat_users = []

    #for chat_user_ref in s.readers:
    #    chat_user = ChatUser.objects.no_dereference().get(id=chat_user_ref.id)
    #    user_fragments = set([f.id for f in chat_user.read_content])
    #    chat_user.story_fragments_count = len(user_fragments & story_fragments)
    #    chat_users.append(chat_user)

    readers_by_fragment = []

    f_p = 1
    print(s.content)
    s_content = sorted(s.content, key=lambda x: x.order)
    for f in s_content:
        if f.type != Fragment.TYPE_ANSWER:
            readers_by_fragment.append({'id':f_p, 'num_readers':f.num_readers})
            f_p += 1

    return render_template('analytics/story.html', s=s, chat_users=chat_users, readers_by_fragment=readers_by_fragment)


@bp.route('/polls')
@login_required
def polls():

    poll_fragments = []

    for bulletin in g.current_account.bulletins:
        for story in bulletin.content:
            for fragment in story.content:
                if fragment.type == Fragment.TYPE_POLL:
                    fragment.text = Emoji.shortcode_to_unicode(fragment.text)
                    poll_fragments.append(fragment)

    polls = PollQuestions.objects(fragment__in=poll_fragments)
    for f in poll_fragments:
        for p in polls:
            if f == p.fragment:
                if not hasattr(f, 'answers'):
                    f.answers = 0
                f.answers += len(p.users)

    return render_template('polls/index.html', poll_fragments=poll_fragments)


@bp.route('/poll/<string:poll_id>')
@login_required
def view_poll(poll_id):

    fragment = Fragment.objects.get_or_404(id=poll_id)

    if fragment.story.bulletin not in g.current_account.bulletins:
        abort(401)

    poll_questions = PollQuestions.objects(fragment=fragment)

    total = float(sum([len(i.users) for i in poll_questions]))

    def get_persent(n, total):
        if total > 0:
            return n / total * 100
        return 0

    data = [{
        'answer': q.text,
        'votes': len(q.users),
        'persent': get_persent(len(q.users), total)} for q in poll_questions]

    # add total stats
    data.append({
        'answer': 'All answers',
        'votes': int(total),
        'persent': 100
    })

    fragment.text = Emoji.shortcode_to_unicode(fragment.text)
    return render_template('polls/questions.html', fragment=fragment, data=data)


@bp.route('/stories/poll/<string:poll_id>/edit', methods=['GET', 'POST'])
@login_required
def stories_poll_edit(poll_id):

    if request.is_xhr:

        fragment = Fragment.objects.get_or_404(id=poll_id)

        if fragment.story.bulletin not in g.current_account.bulletins:
            abort(401)

        poll_questions = PollQuestions.objects(fragment=fragment)

        if request.method == 'GET':

            questions = [{'id': str(i.id), 'text': i.text} for i in poll_questions]
            return jsonify({'text': fragment.text, 'questions': questions})

        elif request.method == 'POST':

            id_to_question = {str(i.id): i for i in poll_questions}

            for index, question in enumerate(request.json['questions']):

                if question.get('id'):
                    poll_question = id_to_question.pop(question['id'])
                    poll_question.text = question['text']
                    poll_question.order = index
                else:
                    poll_question = PollQuestions(fragment=fragment,
                                                  text=question['text'],
                                                  order=index)
                poll_question.save()

            for question in id_to_question.values():
                question.delete()

            fragment.text = request.json['text']
            fragment.save()

        return jsonify({'result': 'ok'})


@bp.route('/chatusers/<string:chat_id>/delete', methods=['POST'])
@login_required
def chatusers_delete(chat_id):
    ChatUser.objects.get_or_404(account_id=g.current_account.id, chat_id=chat_id).delete()
    return redirect(url_for('.chatusers_list'))

@bp.route('/bulletins')
@login_required
def bulletins_list():
    bulletins = []
    tz = timezone(g.current_account.timezone)
    #now = utc.localize(datetime.utc_now()).astimezone(tz)
    now = datetime.now(tz)
    raw_bulletins = Bulletin.objects(account=g.current_account).order_by('-publish_at')
    #for i in g.current_account.bulletins:
    for i in raw_bulletins:
        i.publish_at = utc.localize(i.publish_at).astimezone(tz)
        if not i.is_published:
            i.status = 'DRAFT'
        else:
            if (i.publish_at + timedelta(hours=i.expire_hours)) < now:
                i.status = 'EXPIRED'
            elif i.publish_at > now:
                i.status = 'PENDING'
            elif i.publish_at < now < (i.publish_at + timedelta(hours=i.expire_hours)):
                i.status = 'LIVE'
            else:
                i.status = 'UNKNOWN'

        bulletins.append(i)
    return render_template('bulletins/list.html',
                           bulletins=bulletins)


@bp.route('/bulletins/add', methods=['POST'])
@login_required
def bulletins_add():
    expire_hours_default = app.config['BULLETIN_EXPIRE_HOURS']
    tz = timezone(g.current_account.timezone)
    publish_at = Bulletin.get_default_scheduled_date()

    form = BulletinAddForm(data={
        'expire_hours': expire_hours_default,
        'publish_at': publish_at,
        'is_published': False
    })
    bulletin = Bulletin(account=g.current_account)
    form.populate_obj(bulletin)

    title = publish_at.astimezone(tz).strftime(
        app.config['BULLETIN_NEW_TITLE_FORMAT']
    )
    bulletin.title = title
    bulletin.save()

    g.current_account.bulletins.append(bulletin)
    g.current_account.save()
    return redirect(url_for('.bulletins_edit', bid=bulletin.id))


@bp.route('/bulletins/<string:bid>/publish', methods=['POST'])
@login_required
def bulletins_publish(bid):
    bulletin = Bulletin.objects.get_or_404(account=g.current_account, id=bid)
    t = timezone(g.current_account.timezone)
    bulletin.publish_at = utc.localize(bulletin.publish_at).astimezone(t)

    form = BulletinAddForm(obj=bulletin)
    form.populate_obj(bulletin)

    #TODO: VALIDATE BULLETIN
    bulletin.publish_at = t.localize(bulletin.publish_at).astimezone(utc)
    bulletin.is_published = True
    bulletin.save()

    return redirect(url_for('.bulletins_list'))


@bp.route('/bulletins/<string:bid>/unpublish', methods=['POST'])
@login_required
def bulletins_unpublish(bid):
    bulletin = Bulletin.objects.get_or_404(account=g.current_account, id=bid)

    bulletin.is_published = False
    bulletin.save()

    return redirect(url_for('.bulletins_list'))


@bp.route('/bulletins/<string:bid>/edit', methods=('GET', 'POST'))
@login_required
def bulletins_edit(bid):
    bulletin = Bulletin.objects.get_or_404(account=g.current_account, id=bid)
    t = timezone(g.current_account.timezone)
    bulletin.publish_at = utc.localize(bulletin.publish_at).astimezone(t)
    form = BulletinAddForm(obj=bulletin)

    if form.validate_on_submit():
        form.populate_obj(bulletin)
        t = timezone(g.current_account.timezone)
        bulletin.publish_at = t.localize(bulletin.publish_at).astimezone(utc)
        bulletin.save()

        return redirect(url_for('.bulletins_list'))
    return render_template('bulletins/edit.html',
                           form=form,
                           bulletin=bulletin,
                           action_url=url_for('.bulletins_edit', bid=bid),
                           action_label='Save')


@bp.route('/bulletins/<string:bid>/delete', methods=('POST', ))
@login_required
def bulletins_delete(bid):
    Bulletin.objects.get_or_404(account=g.current_account, id=bid).delete()

    return redirect(url_for('.bulletins_list'))


@bp.route('/bulletins/<string:bid>/order_stories', methods=('POST', ))
@login_required
def bulletins_order_stories(bid):
    bulletin = Bulletin.objects.get_or_404(account=g.current_account, id=bid)

    if bulletin.is_published:
        return (
            jsonify({'ret': 'ERROR', 'msg': 'Unpublish the bulletin first'}),
            400
        )

    form = OrderChangeForm()
    if form.validate_on_submit():
        # story_id: Story object
        current = {str(x.id): x for x in bulletin.content}
        # story_id: Order int
        new = {str(x.object_id.data): x.order.data for x in form.objects}

        if set(current.keys()) != set(new.keys()):
            abort(400)

        for _id, order in new.items():
            current[_id].order = new[_id]
            current[_id].save()

    return jsonify({'ret': 'OK'})


@bp.route('/bulletins/<string:bid>/preview', methods=('GET', ))
@login_required
def bulletins_preview(bid):
    bulletin = Bulletin.objects.get_or_404(
        account=g.current_account, id=bid
    )
    form = BulletinAddForm(obj=bulletin)

    return render_template('bulletins/preview.html',
        bulletin=bulletin, fragment=Fragment, form=form, story=Story)


@bp.route('/stories/<string:bid>/add', methods=('POST',))
@login_required
def stories_add(bid):
    bulletin = Bulletin.objects.get_or_404(account=g.current_account, id=bid)

    tz = timezone(g.current_account.timezone)
    title = datetime.now(utc).astimezone(tz).strftime(
        app.config['BULLETIN_NEW_TITLE_FORMAT']
    )

    story = Story(title=title, lead="")
    story.bulletin = bulletin
    story.order = len(bulletin.content) + 1
    story.save()

    bulletin.content.append(story)
    bulletin.save()

    return redirect(url_for('.stories_edit', sid=story.id))


@bp.route('/stories/<string:sid>/edit', methods=('GET', 'POST'))
@login_required
def stories_edit(sid):
    s = Story.objects.get_or_404(id=sid)

    if s.bulletin not in g.current_account.bulletins:
        abort(401)

    if s.bulletin.is_published:
        return redirect(url_for('.bulletins_list'))

    form = model_form(Story, exclude=['order', 'content', 'bulletin'])
    form = form(request.form, obj=s)

    if form.validate_on_submit():
        form.save()
        return redirect(url_for('.bulletins_edit', bid=s.bulletin.id))

    context = dict(
        fragment=Fragment,
        story=s,
        max_upload_file_size=app.config['MAXIMUM_FILE_UPLOAD_SIZE_MB'],
        sid=sid,
        form=form,
        text_form=model_form(Fragment, exclude=['url', 'type', 'story'])(),
        poll_form=PollForm(),
        action_url=url_for('.stories_edit', sid=sid),
        action_label='Save Story',
        bulletin=s.bulletin,
        skip_poll_message=g.current_account.skip_poll_message
    )

    return render_template('stories/edit.html', **context)


@bp.route('/stories/<string:sid>/delete', methods=('POST', ))
@login_required
def stories_delete(sid):
    s = Story.objects.get_or_404(id=sid)

    if s.bulletin not in g.current_account.bulletins:
        abort(401)

    if s.bulletin.is_published:
        return redirect(url_for('.bulletins_list'))

    url = url_for('.bulletins_edit', bid=s.bulletin.id)

    s.delete()

    return redirect(url)


@bp.route('/stories/<string:sid>/paragraphs/add', methods=('POST', ))
@login_required
def stories_paragraph_add(sid):
    s = Story.objects.get_or_404(id=sid)

    if s.bulletin not in g.current_account.bulletins:
        abort(401)

    if s.bulletin.is_published:
        return redirect(url_for('.bulletins_list'))

    form = TextForm(request.form)

    if form.validate_on_submit():
        validate_fragments_order(s.content, Fragment.TYPE_PARAGRAPH)

        f = Fragment(
            text=form.text.data,
            story=s,
            type=Fragment.TYPE_PARAGRAPH,
            order=len(s.content) + 1
        )
        f.save()

        s.content.append(f)
        s.save()

        return jsonify({
            'ret': 'OK',
            'fragment': f.render_fragment(),
            'is_answer': f.type == f.TYPE_ANSWER
        })

    return Response(response=json.dumps({'errors': form.errors}),
                    status=400,
                    mimetype='application/json')


@bp.route('/stories/<string:sid>/poll/add', methods=['POST'])
@login_required
def stories_poll_add(sid):

    s = Story.objects.get_or_404(id=sid)

    if s.bulletin not in g.current_account.bulletins:
        abort(401)

    if s.bulletin.is_published:
        return redirect(url_for('.bulletins_list'))

    form = PollForm(request.form)

    if form.validate_on_submit():
        validate_fragments_order(s.content, Fragment.TYPE_POLL)

        f = Fragment(
            text=form.text.data,
            story=s,
            type=Fragment.TYPE_POLL,
            order=len(s.content) + 1
        )

        f.save()

        for i, q in enumerate(form.question.data):
            PollQuestions(text=q, fragment=f, order=i).save()

        s.content.append(f)
        s.save()

        return jsonify({
            'ret': 'OK',
            'fragment': f.render_fragment(),
            'is_answer': False
        })

    return Response(response=json.dumps({'errors': form.errors}),
                    status=400,
                    mimetype='application/json')


@bp.route('/stories/<string:sid>/answers/add', methods=('POST', ))
@login_required
def stories_answer_add(sid):
    s = Story.objects.get_or_404(id=sid)

    if s.bulletin not in g.current_account.bulletins:
        abort(401)

    if s.bulletin.is_published:
        return redirect(url_for('.bulletins_list'))

    form = AnswerForm(request.form)

    if form.validate_on_submit():
        validate_fragments_order(s.content, Fragment.TYPE_ANSWER)

        f = Fragment(
            action=form.action.data,
            text=form.text.data,
            story=s,
            type=Fragment.TYPE_ANSWER,
            order=len(s.content) + 1
        )
        f.save()

        s.content.append(f)
        s.save()

        return jsonify({
            'ret': 'OK',
            'fragment': f.render_fragment(),
            'is_answer': f.type == f.TYPE_ANSWER
        })

    return Response(response=json.dumps({'errors': form.errors}),
                    status=400,
                    mimetype='application/json')


@bp.route('/stories/<string:sid>/media/add', methods=('POST', ))
@login_required
def stories_media_add(sid):
    s = Story.objects.get_or_404(id=sid)
    if s.bulletin not in g.current_account.bulletins:
        abort(401)

    if s.bulletin.is_published:
        return redirect(url_for('.bulletins_list'))

    form = UploadMediaForm()
    if form.validate_on_submit():
        media_type = get_media_fragment_type(form.media.data.content_type)
        validate_fragments_order(s.content, media_type)

        url = S3Service().upload(form.media)
        f = Fragment(story=s, text=form.text.data, type=media_type, url=url)
        f.order = len(s.content) + 1
        f.save()

        s.content.append(f)
        s.save()

        return jsonify({
            'ret': 'OK',
            'fragment': f.render_fragment(),
            'is_answer': f.type == f.TYPE_ANSWER
        })

    return Response(response=json.dumps({'errors': form.errors}),
                    status=400,
                    mimetype='application/json')


#and added
@bp.route('/stories/<string:sid>/order_fragments', methods=('POST', ))
@login_required
def stories_order_fragments(sid):
    story = Story.objects.get_or_404(id=sid)

    if story.bulletin not in g.current_account.bulletins:
        abort(401)

    if story.bulletin.is_published:
        return (
            jsonify({'ret': 'ERROR', 'msg': 'Unpublish the bulletin first'}),
            400
        )

    form = OrderChangeForm()

    if form.validate_on_submit():
        # fragment_id: Fragment object
        current = {str(x.id): x for x in story.content}
        # fragment_id: Order int
        new = {str(x.object_id.data): x.order.data for x in form.objects}

        if set(current.keys()) != set(new.keys()):
            abort(400)

        for _id, order in new.items():
            current[_id].order = new[_id]
            current[_id].save()

        return jsonify({'ret': 'OK'})

    return Response(response=json.dumps({'errors': form.errors}),
                    status=400,
                    mimetype='application/json')


@bp.route('/stories/fragment/<string:fid>/update', methods=('PUT', ))
@login_required
def stories_fragment_update(fid):
    f = Fragment.objects.get_or_404(id=fid)

    if f.story.bulletin not in g.current_account.bulletins:
        abort(401)

    if f.story.bulletin.is_published:
        return (
            jsonify({'ret': 'ERROR', 'msg': 'Unpublish the bulletin first'}),
            400
        )

    form = TextForm()
    if form.validate_on_submit():
        f.text = form.text.data
        f.save()

        return jsonify({'ret': 'OK'})

    return Response(response=json.dumps({'errors': form.errors}),
                    status=400,
                    mimetype='application/json')


@bp.route('/stories/<string:sid>/fragment/<string:fid>/delete',
          methods=('POST', ))
@login_required
def fragments_delete(sid, fid):
    s = Story.objects.get_or_404(id=sid)
    f = Fragment.objects.get_or_404(id=fid)

    if s.bulletin not in g.current_account.bulletins:
        abort(401)

    if s.bulletin.is_published:
        return (
            jsonify({'ret': 'ERROR', 'msg': 'Unpublish the bulletin first'}),
            400
        )

    if f.type == Fragment.TYPE_IMAGE:
        S3Service().delete(f.url)

    f.delete()

    return redirect(url_for('.stories_edit', sid=sid))


@bp.route('/audience', methods=('GET', ))
@login_required
def audience():
    account_stats = AccountStats.objects(
        account=g.current_account,
        date__gte=(datetime.today()+timedelta(days=-30))
    ).only(
        'active_users', 'new_users', 'dropped_users',
        'enabled_users', 'messages_received', 'date'
    )
    total_users = ChatUser.objects(account_id=g.current_account, disabled=0).count()

    prev_day = datetime.utcnow() - timedelta(days=1)
    active_users_last24h = AccountStats.objects(
        account=g.current_account,
        date__gte=prev_day.date()
    ).sum('active_users')

    question_fragments = ProfileStoryFragment.objects(
        type=ProfileStoryFragment.TYPE_QUESTION,
        attribute__in=g.current_account.chat_user_attributes
    )
    answers = ChatUserAnswer.objects(
        question__in=question_fragments
    )

    total_users_telegram = ChatUser.objects(account_id=g.current_account,
                                            platform='telegram',
                                            disabled=0).count()

    total_users_facebook = ChatUser.objects(account_id=g.current_account,
                                            platform='facebook',
                                            disabled=0).count()

    total_users_platform = [
        {'title': 'Telegram users', 'value': total_users_telegram},
        {'title': 'Facebook users', 'value': total_users_facebook}
    ]

    return render_template(
        'audience/index.html',
        pathToImages=app.config.get('PATH_TO_AMCHART_IMAGES'),
        account_stats=stats_to_dicts(account_stats),
        total_users=total_users,
        active_users_last24h=int(active_users_last24h),
        questions=group_anwers(answers),
        total_users_platform=total_users_platform,
    )


@bp.route('/audience/details', methods=('GET', ))
@login_required
def audience_details():
    form = AccountStatsDetailForm(request.args)
    if not form.validate():
        abort(400)

    account_stats = AccountStats.objects(
        account=g.current_account, date__gte=form.data['date_from'],
        date__lte=form.data['date_to']).only(
        'active_users', 'new_users', 'dropped_users',
        'enabled_users', 'messages_received', 'date'
    )

    return render_template(
        'audience/details.html',
        pathToImages=app.config.get('PATH_TO_AMCHART_IMAGES'),
        account_stats=stats_to_dicts(account_stats),
        date_from=form.data['date_from'].strftime('%m/%d/%Y'),
        date_to=form.data['date_to'].strftime('%m/%d/%Y')
    )


@bp.route('/about')
def about():
    return render_template('about.html')


@bp.route('/faq')
def faq():
    return render_template('faq.html')


@bp.route('/terms')
def terms():
    return render_template('terms.html')


@bp.route('/user_profiling/attributes/', methods=('GET', ))
@login_required
def user_profiling_attributes():
    return render_template('user_profiling/attribute_list.html',
                           chat_user_attributes=g.current_account.chat_user_attributes,
                           account_id=g.current_account.id)


@bp.route('/user_profiling/attributes/add', methods=('GET', 'POST'))
@login_required
def user_profiling_attribute_add():
    form = ChatUserAttributeAddForm()

    if form.validate_on_submit():
        chat_user_attr = ChatUserAttribute()
        form.populate_obj(chat_user_attr)
        chat_user_attr.save()

        g.current_account.chat_user_attributes.append(chat_user_attr)
        g.current_account.save()

        return redirect(url_for('.user_profiling_attributes', aid=chat_user_attr.id))

    return render_template('user_profiling/attribute_add.html',
                           form=form,
                           action_url=url_for('.user_profiling_attribute_add'),
                           action_label='Save')


@bp.route('/user_profiling/attributes/<string:aid>/edit', methods=('GET', 'POST'))
@login_required
def user_profiling_attribute_edit(aid):
    chat_user_attributes = ChatUserAttribute.objects.get_or_404(id=aid)
    form = ChatUserAttributeAddForm(obj=chat_user_attributes)

    if form.validate_on_submit():
        form.populate_obj(chat_user_attributes)
        chat_user_attributes.save()

        return redirect(url_for('.user_profiling_attributes'))

    return render_template('user_profiling/attribute_edit.html',
                           form=form,
                           chat_user_attributes=chat_user_attributes,
                           action_url=url_for('.user_profiling_attribute_edit', aid=aid),
                           action_label='Save')


@bp.route('/user_profiling/<string:aid>/delete', methods=('POST', ))
@login_required
def user_profiling_attribute_delete(aid):
    ChatUserAttribute.objects.get_or_404(id=aid).delete()
    return redirect(url_for('.user_profiling_attributes'))


@bp.route('/user_profiling/profiling_stories/', methods=('GET', ))
@login_required
def user_profiling_stories():
    return render_template('user_profiling/profile_stories_list.html',
                           profile_stories=ProfileStory.objects(account=g.current_account),
                           fragment=ProfileStoryFragment,
                           account_id=g.current_account.id)


@bp.route('/user_profiling/profiling_stories/add', methods=('GET',))
@login_required
def user_profiling_stories_add():
    # create draft ProfileStory
    story = ProfileStory(
        title='', lead='', account=g.current_account,
        order=ProfileStory.objects(account=g.current_account).count() + 1
    )
    story.save()
    return redirect(url_for('.user_profiling_stories_edit', sid=story.id))


@bp.route('/user_profiling/profiling_stories/<string:sid>/edit', methods=('GET', 'POST',))
@login_required
def user_profiling_stories_edit(sid):
    s = ProfileStory.objects.get_or_404(id=sid, account=g.current_account)

    form = model_form(ProfileStory, exclude=['order', 'content'],
        field_args={
            'title': {'widget': Input(input_type='text')}
        }
    )
    form = form(request.form, obj=s)

    if form.validate_on_submit():
        form.save()
        return redirect(url_for('.user_profiling_stories'))

    return render_template('user_profiling/profile_stories_edit.html',
                           story=s,
                           fragment=ProfileStoryFragment,
                           text_form=model_form(ProfileStoryFragment, exclude=['url', 'type', 'story'])(),
                           form=form,
                           action_label='Save',
                           attributes=g.current_account.chat_user_attributes,
                           action_url=url_for('.user_profiling_stories_edit', sid=sid),
                           account_id=g.current_account.id)


@bp.route('/profile_stories/<string:sid>/delete', methods=('POST', ))
@login_required
def profile_stories_delete(sid):
    ProfileStory.objects.get_or_404(id=sid, account=g.current_account).delete()
    return redirect(url_for('.user_profiling_stories'))


@bp.route('/profile_stories/<string:sid>/paragraphs/add', methods=('POST', ))
@login_required
def profile_stories_paragraph_add(sid):
    s = ProfileStory.objects.get_or_404(id=sid, account=g.current_account)

    form = TextForm(request.form)
    if form.validate_on_submit():
        validate_fragments_order(s.content, ProfileStoryFragment.TYPE_PARAGRAPH)

        f = ProfileStoryFragment(
            text=form.text.data,
            story=s,
            type=ProfileStoryFragment.TYPE_PARAGRAPH,
            order=len(s.content) + 1
        )
        f.save()

        s.content.append(f)
        s.save()

        return jsonify({
            'ret': 'OK',
            'fragment': f.render_fragment(),
            'is_answer': f.type == f.TYPE_ANSWER
        })

    return Response(response=json.dumps({'errors': form.errors}),
                    status=400,
                    mimetype='application/json')


@bp.route('/profile_stories/<string:sid>/answers/add', methods=('POST', ))
@login_required
def profile_stories_answer_add(sid):
    s = ProfileStory.objects.get_or_404(id=sid, account=g.current_account)
    form = AnswerForm(request.form)

    if form.validate_on_submit():
        validate_fragments_order(s.content, ProfileStoryFragment.TYPE_ANSWER)

        f = ProfileStoryFragment(
            action=form.action.data,
            text=form.text.data,
            story=s,
            type=ProfileStoryFragment.TYPE_ANSWER,
            order=len(s.content) + 1
        )
        f.save()

        s.content.append(f)
        s.save()

        return jsonify({
            'ret': 'OK',
            'fragment': f.render_fragment(),
            'is_answer': f.type == f.TYPE_ANSWER
        })

    return Response(response=json.dumps({'errors': form.errors}),
                    status=400,
                    mimetype='application/json')


@bp.route('/profile_stories/fragment/<string:fid>/update', methods=('PUT', ))
@login_required
def profile_stories_fragment_update(fid):
    f = ProfileStoryFragment.objects.get_or_404(id=fid)
    if f.type == ProfileStoryFragment.TYPE_QUESTION:
        form = QuestionForm()
    else:
        form = TextForm()

    if form.validate_on_submit():
        f.text = form.text.data
        if f.type == ProfileStoryFragment.TYPE_QUESTION:
            f.attribute = form.attribute

        f.save()

        return jsonify({'ret': 'OK'})

    return Response(response=json.dumps({'errors': form.errors}),
                    status=400,
                    mimetype='application/json')


@bp.route('/profile_stories/<string:sid>/fragment/<string:fid>/delete',
          methods=('POST', ))
@login_required
def profile_fragments_delete(sid, fid):
    f = ProfileStoryFragment.objects.get_or_404(id=fid)
    f.delete()
    return redirect(url_for('.user_profiling_stories_edit', sid=sid))


@bp.route('/profile_stories/<string:sid>/activate/', methods=('PUT', ))
@login_required
def profile_story_activate_ajax(sid):
    form = ActivateForm()
    if not form.validate_on_submit():
        return jsonify({'errors': form.errors}), 400

    story = ProfileStory.objects(id=sid, account=g.current_account).first()

    if request.is_xhr:
        if story:
            # update question status
            story.active = form.active.data
            story.save()
            return jsonify({'ret': 'OK', 'active': story.active})
        else:
            return jsonify({
                'ret': 'ERROR',
                'msg': 'Profile story with given id do not exists'
            }), 400

    return redirect(url_for('.user_profiling_stories'))


@bp.route('/profile_stories/<string:sid>/questions/add', methods=('POST', ))
@login_required
def profile_stories_question_add(sid):
    s = ProfileStory.objects.get_or_404(id=sid, account=g.current_account)

    form = QuestionForm(request.form)
    if form.validate_on_submit():
        validate_fragments_order(s.content, ProfileStoryFragment.TYPE_QUESTION)

        f = ProfileStoryFragment(
            text=form.text.data,
            attribute=form.attribute,
            story=s,
            type=ProfileStoryFragment.TYPE_QUESTION,
            order=len(s.content) + 1
        )
        f.save()

        s.content.append(f)
        s.save()

        return jsonify({
            'ret': 'OK',
            'fragment': f.render_fragment(),
            'is_answer': f.type == f.TYPE_ANSWER
        })

    return Response(response=json.dumps({'errors': form.errors}),
                    status=400,
                    mimetype='application/json')


@bp.route('/profile_stories/order_stories', methods=('POST', ))
@login_required
def profile_stories_order():
    form = OrderChangeForm()
    if form.validate_on_submit():
        # story_id: ProfileStory object
        stories = ProfileStory.objects(account=g.current_account)
        current = {str(s.id): s for s in stories}
        # story_id: Order int
        new = {str(x.object_id.data): x.order.data for x in form.objects}

        if set(current.keys()) != set(new.keys()):
            abort(400)

        for _id, order in new.items():
            current[_id].order = new[_id]
            current[_id].save()

    return jsonify({'ret': 'OK'})


@bp.route('/profile_stories/<string:sid>/order_fragments', methods=('POST', ))
@login_required
def profile_stories_order_fragments(sid):
    story = ProfileStory.objects.get_or_404(id=sid, account=g.current_account)
    form = OrderChangeForm()

    if form.validate_on_submit():
        # fragment_id: ProfileStoryFragment object
        current = {str(x.id): x for x in story.content}
        # fragment_id: Order int
        new = {str(x.object_id.data): x.order.data for x in form.objects}

        if set(current.keys()) != set(new.keys()):
            abort(400)

        for _id, order in new.items():
            current[_id].order = new[_id]
            current[_id].save()

        return jsonify({'ret': 'OK'})

    return Response(response=json.dumps({'errors': form.errors}),
                    status=400,
                    mimetype='application/json')
