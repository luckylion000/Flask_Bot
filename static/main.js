/* eslint-disable no-unused-vars */

/**
 *  initialize datetimepicker widget
 */
function initCalendarWidget() {
    $('#datetimepicker1').datetimepicker({
        format: 'M/D/YYYY',
        sideBySide: true
    });

    $('.clockpicker').clockpicker({
        placement: 'top',
        align: 'top',
        autoclose: true,

        afterShow: function() {
            if ($('#send_immediately').is(':checked') || bulletinIsPublished) {
                $('.clockpicker').clockpicker('hide');
            }
        }
    });
}

/**
 *  bind show event to backendErrorModal modal
 */
function initModalBackendError() {
    $('#backendErrorModal').on('show.bs.modal', function(event) {
        $(this).find('.modal-body').text($(this).data('text'));
    });
}

/**
 *  display error in backendErrorModal modal
 *  @param {object} ret jQuery AJAX response object
 */
function modalBackendError(ret) {
    $('#backendErrorModal').data(
        'text', ret.status + ' ' + ret.responseText);
    $('#backendErrorModal').modal({
        keyboard: false,
        backdrop: 'static'
    });
}
/* eslint-enable no-unused-vars */

$(document).ready(function() {
    $('#confirm-delete').on('show.bs.modal', function(e) {
        $(this).find('form').attr('action', $(e.relatedTarget).data('href'));
    });
    $('#confirm-publish').on('show.bs.modal', function(e) {
        $(this).find('form').attr('action', $(e.relatedTarget).data('href'));
    });

	//analitics
	$('#analitics_from, #analitics_to').parent().datepicker({
        format: "mm/dd/yyyy",
        sideBySide: true
    }).on('dp.change',function(){$(this).parents('form').trigger('submit');});;

	$('#analitics_from, #analitics_to, #analitics_sort')
        .change(function(){$(this).parents('form').trigger('submit');});
});

/**
 * build pie chart using AmCharts library
 */
function render_pie_chart(id, dataProvider, titleField) {
    AmCharts.makeChart(id,
        {
            "type": "pie",
            "balloonText": "[[title]]<br><span style='font-size:14px'>" +
                "<b>[[value]]</b> ([[percents]]%)</span>",
            "titleField": titleField,
            "valueField": "value",
            "allLabels": [],
            "balloon": {},
            "legend": {
                "enabled": true,
                "align": "center",
                "markerType": "circle"
            },
            "titles": [],
            "dataProvider": dataProvider
        }
    );
}

/**
 * build serial chart using AmCharts library
 */
function render_serial_chart(id, dataProvider, categoryField,
    title, pathToImages) {

    AmCharts.makeChart(id,
        {
            "type": "serial",
            "categoryField": categoryField,
            "startDuration": 1,
            "pathToImages": pathToImages,
            "categoryAxis": {
                "gridPosition": "start"
            },
            "trendLines": [],
            "graphs": [
                {
                    "balloonText": "[[title]] of [[" + categoryField + "]]:[[value]]",
                    "fillAlphas": 1,
                    "id": "AmGraph-1",
                    "title": title,
                    "type": "column",
                    "valueField": "value"
                }
            ],
            "dataProvider": dataProvider
        }
    );
}

/**
 * build user growth chart using AmCharts library
 * for audience index page
 */
function render_user_growth_chart(id, dataProvider, categoryField, pathToImages) {
    AmCharts.makeChart(id,
        {
            "type": "serial",
            "categoryField": categoryField,
            "columnSpacing": 0,
            "sequencedAnimation": false,
            "pathToImages": pathToImages,
            "categoryAxis": {
                "autoRotateCount": 4,
                "gridPosition": "start",
                "parseDates": true
            },
            "chartCursor": {
                "enabled": true
            },
            "chartScrollbar": {
                "enabled": true
            },
            "trendLines": [],
            "graphs": [
                {
                    "fillAlphas": 1,
                    "fillColors": "#00CB0F",
                    "legendColor": "#00CB0F",
                    "id": "AmGraph-1",
                    "lineAlpha": 0,
                    "lineThickness": 0,
                    "title": "active users",
                    "type": "column",
                    "valueField": "active_users"
                },
                {
                    "columnWidth": 0.8,
                    "fillAlphas": 1,
                    "fillColors": "#017803",
                    "legendColor": "#017803",
                    "id": "AmGraph-2",
                    "lineThickness": 0,
                    "title": "new users",
                    "newStack": true,
                    "type": "column",
                    "valueField": "new_users"
                },
                {
                    "cornerRadiusTop": 1,
                    "customMarker": "",
                    "id": "AmGraph-3",
                    "lineColor": "#FF0000",
                    "lineThickness": 4,
                    "title": "dropped users",
                    "valueField": "dropped_users",
                    "yAxis": "ValueAxis-2"
                },
                {
                    "id": "AmGraph-4",
                    "title": "enabled users",
                    "valueField": "enabled_users",
                    "lineColor": "#219651",
                    "lineThickness": 4,

                }
                /*,
                {
                    "id": "AmGraph-5",
                    "title": "messages received",
                    "valueField": "messages_received"
                }
                */
            ],
            "guides": [],
            "valueAxes": [
                {
                    "id": "ValueAxis-1",
                    "stackType": "regular",
                    "labelOffset": -6,
                    "title": "Users"
                },
                {
                    "id": "ValueAxis-2",
                    "position": "right",
                    "title": "mm"
                }
            ],
            "allLabels": [],
            "balloon": {},
            "legend": {
                "enabled": true
            },
            "titles": [
                {
                    "id": "Title-1",
                    "size": 24,
                    'color': '#676a6c',
                    "text": "User Growth"
                }
            ],
            "dataProvider": dataProvider
        }
    );
}

function publishModalText(is_immediately, publish_at) {
    if(!is_immediately) {
        var _text = 'Are you sure you want this bulletin ' +
                'to be published on <strong>' + publish_at + '</strong>';
    } else {
        var _text = 'This bulletin will be published now! Are you sure? ' +
            'Remember that you can schedule the bulletin to be ' +
            'sent later clicking on "schedule"';
    }

    $('#confirm-publish p').html(_text);
}
