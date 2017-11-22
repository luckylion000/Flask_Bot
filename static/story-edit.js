/* eslint-disable no-unused-vars */

/**
 *  display error in backendErrorModal modal
 *  @param {string} typeAnswer Fragment.TYPE_ANSWER
 *  @param {string} orderSaveUrl url to POST new order of fragments
 *  @param {bool} bulletinIsPublished prohibit any action if
 *  bulletinIsPublished
 */


function initPollEdit() {

    var form_tpl = $('#edit-fragment-type-l').children('span');

    form_tpl.find('button.btn-question-add').click(function(e) {

        var form = $(this).closest('.edit-poll-form');
        var poll_questions = form.find('.poll-questions');

        var first_question = poll_questions.find('div.input-group').first();
        var new_question = first_question.clone();

        new_question.find('input').val('');
        new_question.find('input').data('id', '');

        new_question.insertBefore(poll_questions.find('div.input-group:last'));
        return false;

    });

    form_tpl.find('.poll-questions').on('click', 'button.btn-question-remove', function(e) {

        var form = $(this).closest('.edit-poll-form');
        var poll_questions = form.find('.poll-questions');

        if (poll_questions.find('div.input-group').size() > 1) {
            $(this).closest('div.input-group').remove();
        }

        return false;
    });

    form_tpl.find('.fragment-edit-save').click(function(e) {

        var form = $(this).closest('.edit-poll-form');
        var poll_questions = form.find('.poll-questions');

        var data = { questions: [] };
        data.text = emojione.toShort(form.find('textarea').val());

        poll_questions.find('.input-group').each(function(index, input_group) {
            var input = $(input_group).find('input');
            data.questions.push({'id': input.data('id'), 'text': input.val()})
        });

        var url = '/stories/poll/' + form.data('id') + '/edit';

        $.ajax(url, {
            type: 'POST',
            data: JSON.stringify(data),
            contentType: 'application/json',
            success: function(result) {
                form.data('save_promise').resolve(data);
            }
        });
    });

    form_tpl.on('initialize', function(e) {

        var form = $(this).closest('.edit-poll-form');
        var poll_questions = form.find('.poll-questions');

        var url = '/stories/poll/' + form.data('id') + '/edit';

        $.get(url, function(data) {

            var first_question = poll_questions.find('.input-group').first();
            var input = first_question.find('input');
            input.val(data.questions[0].text);
            input.data('id', data.questions[0].id);

            var rest_questions = data.questions.splice(1);
            for (var i in rest_questions) {
                var new_question = first_question.clone();
                new_question.find('input').val(rest_questions[i].text);
                new_question.find('input').data('id', rest_questions[i].id);
                poll_questions.append(new_question);
            }

            form.find('textarea').val(data.text);
            form.find('textarea').emojioneArea({
                events: {
                    keyup: update_editor_counter,
                    paste: update_editor_counter,
                    emojibtn_click: update_editor_counter
                }
            });

            form.data('init_promise').resolve();
            // initialize counter
            $("div.emojionearea-editor").trigger("keyup");
        });
    });
}

function initPollAdd() {

    var form = $('.add-poll-form');
    var poll_questions = form.find('.poll-questions');

    var poll_questions_rename = function() {
        poll_questions.find('div.input-group').map(function(index, elem) {
            $(elem).find('input').attr('name', 'question-' + index);
        });
    };

    form.find('button.btn-poll-question-add').click(function(e) {
        var firstEntry = poll_questions.find('div.input-group:first');
        var newEntry = firstEntry.clone();
        newEntry.find('input').val('');
        // insert new option before last
        newEntry.insertBefore(poll_questions.find('div.input-group:last'));
        poll_questions_rename();
        return false;
    });

    poll_questions.on('click', '.btn-poll-question-remove', function(e) {

        if (poll_questions.find('div.input-group').size() > 1) {
            $(this).closest('div.input-group').remove();
            poll_questions_rename();
        }

        return false;
    });
}

function initStoryEdit(typeAnswer, orderSaveUrl, bulletinIsPublished) {
    initModalBackendError();
    initPollEdit();
    initPollAdd();

    // init should be before emojione.shortnameToImage
    $('.emoji-input').emojioneArea({
        events: {
            keyup: update_editor_counter,
            paste: update_editor_counter,
            emojibtn_click: update_editor_counter
        }
    });

    // init lead counter
    $('#lead, #title').on('input propertychange', function(e) {
        var len = $(this).val().length;
        var lead_form = $($(this).parent()).parent();
        $(lead_form).find('input.fragment-edit-counter').val(len);
    })
    $('#lead, #title').trigger('input');

    $('.bubble .emoji-container').each(function(idx) {
        var t = emojione.shortnameToImage($(this).html());
        $(this).html(t);
    });

    if (bulletinIsPublished) {
        $('#add-paragraph, #add-media, #add-answer, #add-poll').prop('disabled', true);
        $('.bubble-actions-container button').prop('disabled', true);
        $('.bubble-internal-actions-container button').prop('disabled', true);
        return;
    }

    var getCurrentTypes = function() {
        return $('.fragments-container .bubble-body').map(function() {
            return $(this).data('fragmentType');
        }).get();
    };

    if (getCurrentTypes().length === 0) {
        $('#add-paragraph, #add-media, #add-poll').prop('disabled', true);
    } else if($(getCurrentTypes()).get(-1) === 'l') {
        // If last fragment is a poll, disable "add answer" button
        $('#add-answer').prop('disabled', true);
    }

    $('#control-buttons').on('click', function(e) {
        e.preventDefault();
        disableControls();
        disableSortable();

        $(this).hide();
        var formSelector = '.' + e.target.id + '-form';
        $(formSelector).removeClass('hidden');
        $(formSelector + ' textarea').focus();
    });

    $('button[type=reset]').on('click', function(e) {
        $('#control-buttons').show();
        var form = $(this).closest('form');
        form.closest('div').addClass('hidden');
        e.preventDefault();
        enableControls();
        enableSortable();
    });

    var bSel = '.bubble-body[data-fragment-id]';
    var saveOrder = function(bubble) {
        var data = {};

        bubble.closest('.fragments-container').find(bSel).each(function(idx) {
            var idKey = 'objects-' + idx + '-object_id';
            var orderKey = 'objects-' + idx + '-order';

            data[idKey] = $(this).data('fragmentId');
            data[orderKey] = idx + 1;
        });

        $.post(orderSaveUrl, data, function(ret) {
            // success
        }).fail(function(ret) {
            modalBackendError(ret);
        });
    };
    var isAnswerBubble = function(b) {
        return b.data('fragmentType') === typeAnswer;
    };
    var toggleButtonsState = function() {
        // Enable all order buttons
        $('.increase-order, .decrease-order').prop('disabled', false);

        // External action containers
        $('.bubble:first-child .bubble-actions-container')
            .find('.increase-order').prop('disabled', true);
        $('.bubble:last-child .bubble-actions-container')
            .find('.decrease-order').prop('disabled', true);

        // Internal action containers
        $('.bubble').find('.bubble-body-answer:first')
            .find('.increase-order').prop('disabled', true);
        $('.bubble').find('.bubble-body-answer:last')
            .find('.decrease-order').prop('disabled', true);

        if (!isAnswerBubble($('.bubble').eq(0))) {
            $('.bubble')
                .eq(1)
                .find('.bubble-actions-container .increase-order')
                .prop('disabled', true);
        }
        if (!isAnswerBubble($('.bubble').eq(1))) {
            $('.bubble')
                .eq(0)
                .find('.bubble-actions-container .decrease-order')
                .prop('disabled', true);
        }
    };
    toggleButtonsState();

    // We have to disable sortable when whetering to an 'edit' state, because
    // it is not possible to focus on edit field (start editing) when
    // sortable is active.
    var disableSortable = function() {
        $('.fragments-container, .bubble-answers-group').sortable('disable');
    };
    var enableSortable = function() {
        $('.fragments-container, .bubble-answers-group').sortable('enable');
    };

    $('.fragments-container').sortable({
        cursor: 'move',
        update: function(event, ui) {
            if (!isAnswerBubble($('.bubble-body').first())) {
                $('.fragments-container').sortable('cancel');
                return;
            }

            saveOrder(ui.item);
            toggleButtonsState();
            ui.item.effect("highlight", {}, 1000);
        }
    });

    var bubble_answer_group_options = {
        cursor: 'move',
        update: function(event, ui) {
            saveOrder(ui.item);
            toggleButtonsState();
            ui.item.effect("highlight", {}, 1000);
        }
    };

    $('.bubble-answers-group ').sortable(bubble_answer_group_options);

    $('body').on('click', '.increase-order', function(e) {
        e.preventDefault();

        var target = $(e.target);
        var sel = '.bubble';
        if ($(e.target).parent().is('.bubble-internal-actions-container')) {
            sel = '.bubble-body';
        } else {
            var bubble = target.closest(sel);
            if (bubble.index() === 1 &&
                    !isAnswerBubble(bubble.find('.bubble-body').first())) {
                return;
            }
        }

        var b = target.closest(sel);
        if (b.prev().is(sel)) {
            b.insertBefore(b.prev());
            b.effect("highlight", {}, 1000);
            saveOrder(b);
            toggleButtonsState();
        }
    });

    $('body').on('click', '.decrease-order', function(e) {
        e.preventDefault();

        var target = $(e.target);
        var sel = '.bubble';
        if ($(e.target).parent().is('.bubble-internal-actions-container')) {
            sel = '.bubble-body';
        } else {
            var bubble = target.closest(sel);
            if (bubble.index() === 0 &&
                    !isAnswerBubble(
                        bubble.next(sel).find('.bubble-body').first())) {
                return;
            }
        }

        var b = $(e.target).closest(sel);
        if (b.next().is(sel)) {
            b.insertAfter(b.next());
            b.effect("highlight", {}, 1000);
            saveOrder(b);
            toggleButtonsState();
        }
    });

    var disableControls = function() {
        $('.bubble-actions-container, .bubble-internal-actions-container').find('button').prop('disabled', true);
        $('#control-buttons').find('button').prop('disabled', true);
        $('#story-save').prop('disabled', true);
    };
    var enableControls = function() {
        $('.bubble-actions-container, .bubble-internal-actions-container').find('button').prop('disabled', false);
        $('#control-buttons').find('button').prop('disabled', false);
        $('#story-save').prop('disabled', false);

        if($(getCurrentTypes()).get(-1) === 'l') {
            // If last fragment is a poll, disable "add answer" button
            $('#add-answer').prop('disabled', true);
        }
    };

    $('body').on('click', '.edit-poll-fragment', function(e) {
        e.preventDefault();

        var poll_id = $(this).data('fragmentId');
        var contentContainer = $('.fragments-container').find('.content-container-' + poll_id);
        var inputContainer = $('.fragments-container').find('.input-container-' + poll_id);

        var form_tpl = $('#edit-fragment-type-l').children('span');

        var form = form_tpl.clone(true);
        form.data('id', poll_id);
        form.data('init_promise', $.Deferred());
        form.data('save_promise', $.Deferred());
        form.trigger('initialize');

        form.data('init_promise').done(function() {

            disableControls();
            disableSortable();

            inputContainer.html(form);
            contentContainer.hide();
            form.removeClass('hidden');
            inputContainer.removeClass('hidden');

            form.find('.fragment-edit-cancel').on('click', function(e) {

                form.remove();
                inputContainer.addClass('hidden');
                contentContainer.show();

                enableControls();
                enableSortable();
            });

            form.find('.fragment-edit-save').click(function(e) {
                form.data('save_promise').done(function(data) {

                    var questions = contentContainer.find('.show-poll-questions');

                    questions.find('li').remove();
                    for (var i in data.questions) {
                        questions.find('ul').append($('<li>' + data.questions[i].text + '</li>'));
                    }

                    contentContainer.find('.emoji-container').text(data.text);
                    var html_safe = contentContainer.find('.emoji-container').html();
                    contentContainer.find('.emoji-container').html(emojione.shortnameToImage(html_safe));

                    form.remove();
                    inputContainer.addClass('hidden');
                    contentContainer.show();

                    enableControls();
                    enableSortable();
                })
            });
        });
    });

    $('.add-question-form, .add-paragraph-form, .add-answer-form,' +
        '.add-poll-form, .add-media-form').on('submit', 'form', function(e) {

        // send add-fragment form via ajax
        var self = this;
        var inputContainer = $(self).find('.bubble-body').eq(0);
        var helpBlock = $(self).find('.help-block').eq(0);

        var input = $(self).find('.emoji-input').eq(0);
        if (input.length != 0) {
            input.val(emojione.toShort(input.val()));
        }

        $.ajax({
            type: 'POST',
            url: $(self).attr('action'),
            data: new FormData(self),
            cache: false,
            contentType: false,
            processData: false,

            success: function(response) {
                if (response.is_answer) {
                    // TODO: if last fragment answer remove it
                    // else append answer as a new fragment
                    var f = $('.fragments-container div.bubble').last();
                    if ($(f).hasClass("bubble-answers-group")) {
                        f.remove();
                    }
                }

                $('.fragments-container').append(response.fragment);
                $('.fragments-container').sortable("refresh");
                var new_fragment = $('.fragments-container .bubble').last()
                new_fragment.effect("highlight", {}, 1000);

                if (response.is_answer) {
                    $(".bubble-answers-group").not('.ui-sortable')
                        .sortable(bubble_answer_group_options);
                }

                // remove errors text
                helpBlock.text("");
                inputContainer.removeClass('has-error');
                // clear form fields
                $(self).find("input[type=text], input[type=file]").val("");

                $(self).find('button[type=reset]').trigger('click');

                if (input.length != 0) {
                    // clear emojione textbox
                    input.data('emojioneArea').setText("");

                    var fId = $(new_fragment)
                        .find('.bubble-body')
                        .data('fragmentId');

                    var content = $('.fragments-container')
                        .find('.content-container-' + fId);

                    show_emojione(content);
                }

                // update ordering buttons
                toggleButtonsState();

                // if poll created
                // reset poll options
                var poll_questions = $(self).find('div.poll-questions');
                if (poll_questions) {
                    reset_poll_questions(poll_questions);
                }
            },
            error: function(ret) {
                show_fragment_errors(ret, inputContainer, helpBlock);
            }
        });

        e.preventDefault();
    });

    $('body').on('click', '.edit-fragment', function(e) {
        e.preventDefault();

        disableControls();
        disableSortable();

        var fId = $(this).data('fragmentId');
        var content = $('.fragments-container')
            .find('.content-container-' + fId);
        var inputContainer = $('.fragments-container')
            .find('.input-container-' + fId);

        var originalText = content
                .children('.original-text-container').eq(0).text();
        var originalAttrId = content
                .children('.original-attribute-container').eq(0).text();

        var formSel = '#edit-fragment-type-' + content.data('fragmentType');
        var span = $(formSel).children('span').eq(0).clone()
                .appendTo(inputContainer);

        content.hide();

        var textarea = span.children('textarea').eq(0);
        // WARNING: only question fragments have attribute field
        var attribute = span.find('select[name="attribute"]').eq(0);
        attribute.val(originalAttrId);

        textarea.val(originalText);
        inputContainer.removeClass('hidden');

        textarea.show();
        textarea.emojioneArea({
            events: {
                keyup: update_editor_counter,
                paste: update_editor_counter,
                emojibtn_click: update_editor_counter
            }
        });

        // initialize counter
        $("div.emojionearea-editor").trigger("keyup");

        span.children('.fragment-edit-cancel').on('click', function(e) {
            $(this).off('click');
            span.remove();
            inputContainer.addClass('hidden');
            content.show();

            enableControls();
            enableSortable();
        });

        span.children('.fragment-edit-save').on('click', function(e) {
            var self = this;
            var saveUrl = content.parents('.bubble-body').eq(0).data('saveUrl');
            var text = emojione.toShort(textarea.val());
			$(this).parents('.bubble-body').find('.doc-name').html(text);

            var save_form_data = {text: text};
            if (attribute) {
                // question fragment, put attribute in requests
                save_form_data.attribute = attribute.val();
            }

            $.ajax({
                url: saveUrl,
                type: 'PUT',
                data: save_form_data
            }).done(function(ret) {
                $(self).off('click');
                span.remove();
                inputContainer.addClass('hidden');

                content.children('.original-text-container').eq(0).text(text);
                content.children('.original-attribute-container').eq(0).text(save_form_data.attribute);

                show_emojione(content)
                enableControls();
                enableSortable();

                // update ordering buttons
                toggleButtonsState();
            }).fail(function(ret) {
                var helpBlock = span.children('.help-block').eq(0);
                show_fragment_errors(ret, inputContainer, helpBlock)
            });
        });
    });
}

function update_editor_counter(editor, event) {
    var container = $($(this.editor).parent()).parent();
    // NOTE: ignoring new-line character
    var char_count = this.getText().replace('\n', '').length;
    if (container.find('input.fragment-edit-counter').length == 0) {
        container = container.parent();
    }
    container.find('input.fragment-edit-counter').val(char_count);
}

function show_fragment_errors(ret, inputContainer, helpBlock) {
    var text = '';

    if (ret.status === 400) {
        if ('errors' in ret.responseJSON.errors) {
            text = JSON.stringify(ret.responseJSON.errors[0]);
        } else {
            text = ret.responseText;
        }
    } else {
        text = ret.status + ' ' + ret.statusText;
    }

    inputContainer.addClass('has-error');
    helpBlock.text(text);
    helpBlock.removeClass('hidden');
}

function show_emojione(content) {
    var html_safe = content.children('.original-text-container').eq(0).html();
    if (!html_safe) {
        html_safe = content.find('.emoji-container').html();
    }
    var text = emojione.shortnameToImage(html_safe);
    content.children('.emoji-container').eq(0).html(text);
    content.show();
}

function reset_poll_questions(poll_questions) {
    var skip_poll_message = poll_questions.find('#skip_msg').text();

    if (poll_questions.find('div.input-group').size() == 1) {
        console.log("1 element");
        var first_question = poll_questions.find('div.input-group:first');
        var new_question = first_question.clone();
        new_question.insertAfter(first_question);
    } else {
        // keep only firt 2 questions
        // and remove the rest
        poll_questions.find('div.input-group').slice(2).remove();
    }

    poll_questions.find('div.input-group').eq(0).find('input').val('option1');
    poll_questions.find('div.input-group').eq(1)
        .find('input').val(skip_poll_message)
        .attr('name', 'question-1');
}
/* eslint-enable no-unused-vars */
