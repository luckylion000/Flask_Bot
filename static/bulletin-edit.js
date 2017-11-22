$(document).ready(function() {
    initCalendarWidget();
    initModalBackendError();

    $('#send_immediately').on('change', function(e) {

        if ($(this).is(':checked')) {
            var now = new Date;
            $('#datetimepicker1').data("DateTimePicker").date(now).disable();
            $('.clockpicker').find('input').val(now.getHours() + ":" + now.getMinutes());

            $('.clockpicker').find('input')
                .attr("readonly", "")
                .attr('disabled','disabled');

            /* Was in Master - conflict
            var now = new Date();
            console.log(now);
            $('#datetimepicker1').data("DateTimePicker").date(now).disable();
            */
            $('#datetimepicker1').find('#publish_at')
                .removeAttr("disabled")
                .attr("readonly", "");

        } else {
            $('#datetimepicker1').find('#publish_at')
                .removeAttr("readonly");

            $('#datetimepicker1').data("DateTimePicker").enable();
            $('.clockpicker').find('input')
                .removeAttr("readonly")
                .removeAttr("disabled");
        }
    });

    $('#publish').on('click', function(e) {
        $('#publish_at').val(
            $('#publish_at').val() + " " + $('input[name="publish_at_time"]').val()
        );

        $("#save_form").attr("action", publishBulletinUrl).submit();
    });

    $('#unpublish').on('click', function(e) {
        $("#save_form").attr("action", unpublishBulletinUrl).submit();
    });

    $('#save_draft').on('click', function(e) {
        $('#publish_at').val(
            $('#publish_at').val() + " " + $('input[name="publish_at_time"]').val()
        );

        $("#save_form").attr("action", saveBulletinUrl).submit();
    });

    if (bulletinIsPublished) {
        $('.clockpicker').find('input')
            .attr("readonly", "")
            .attr('disabled','disabled');

        // Add story button should be disabled.
        $('#add_story').addClass("disabled");
        // Stories cannot be deleted or edited.
        $('.story-actions-container button').prop('disabled', true);
        return;
    }

    var trSel = 'tr[data-story-order]';
    var saveOrder = function(tr) {
        var data = {};

        tr.parent().children(trSel).each(function(idx) {
            var idKey = 'objects-' + idx + '-object_id';
            var orderKey = 'objects-' + idx + '-order';

            data[idKey] = $(this).data('storyId');
            data[orderKey] = idx + 1;
        });

        $.post(orderSaveUrl, data, function(ret) {
            // success
        }).fail(function(ret) {
            modalBackendError(ret);
        });
    };
    var toggleButtonsState = function() {
        $('.increase-order, .decrease-order').prop('disabled', false);
        $('table').find('tr:first-child .increase-order')
            .prop('disabled', true);
        $('table').find('tr:last-child .decrease-order')
            .prop('disabled', true);
    };
    toggleButtonsState();

    $('.bulletin-stories-table tbody').sortable({
        cursor: 'move',
        update: function(event, ui) {
            saveOrder(ui.item);
            toggleButtonsState();
            ui.item.effect("highlight", {}, 1000);
        }
    });

    $('.increase-order').on('click', function(e) {
        e.preventDefault();

        var tr = $(e.target).parents(trSel).eq(0);
        if (tr.prev().is(trSel)) {
            tr.insertBefore(tr.prev());
            tr.effect("highlight", {}, 1000);
            saveOrder(tr);
            toggleButtonsState();
        }
    });

    $('.decrease-order').on('click', function(e) {
        e.preventDefault();

        var tr = $(e.target).parents(trSel).eq(0);
        if (tr.next().is(trSel)) {
            tr.insertAfter(tr.next());
            tr.effect("highlight", {}, 1000);
            saveOrder(tr);
            toggleButtonsState();
        }
    });

    // handle add_story form
    $('#add_story').on('click', function(e) {
        var form = $(this).parent();
        e.preventDefault();

        var newForm = $('<form>', {
            'action': form.data('action'),
            'method': 'POST'
        }).append($('<input>', {
            'name': 'csrf_token',
            'value':  $(form).find('#csrf_token').val(),
            'type': 'hidden'
        }));

        newForm.appendTo('body').submit().remove();
    })
});
