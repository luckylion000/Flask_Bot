import os.path

from flask_assets import Bundle, Environment


def setup_assets(app):
    assets = Environment(app)
    assets.url_expire = True

    assets.cache = False
    assets.manifest = False
    assets.load_path = [
        os.path.join(app.config['PROJECT_ROOT'], 'static'),
        os.path.join(app.config['PROJECT_ROOT'], 'bower_components')
    ]

    css_main = Bundle(
        'bootstrap/dist/css/bootstrap.min.css',
        'bootstrap-toggle/css/bootstrap-toggle.min.css',
        'awesome-bootstrap-checkbox/awesome-bootstrap-checkbox.css',
        'datatables/media/css/jquery.dataTables.min.css',
        'datatables/media/css/dataTables.bootstrap.min.css',
        'bootstrap-datepicker/dist/css/bootstrap-datepicker.min.css',
        'clockpicker/dist/bootstrap-clockpicker.min.css',
        'eonasdan-bootstrap-datetimepicker/build/css/bootstrap-datetimepicker.min.css',  # NOQA
        'emojione/assets/css/emojione.min.css',
        'emojionearea/dist/emojionearea.min.css',
        'js/plugins/export/export.css',
        'main.css',
        # inspinia theme files
        'inspinia_v2.7.1/css/style.css',
        'inspinia_v2.7.1/css/animate.css',
        'inspinia_v2.7.1/font-awesome/css/font-awesome.min.css',
    )
    js_main = Bundle(
        'jquery/dist/jquery.min.js',
        'jquery-ui/jquery-ui.min.js',
        'bootstrap/dist/js/bootstrap.min.js',
        'bootstrap-toggle/js/bootstrap-toggle.min.js',
        'datatables/media/js/jquery.dataTables.min.js',
        'datatables/media/js/dataTables.bootstrap.min.js',
        'moment/min/moment-with-locales.min.js',
        'bootstrap-datepicker/dist/js/bootstrap-datepicker.min.js',
        'clockpicker/dist/bootstrap-clockpicker.min.js',
        'eonasdan-bootstrap-datetimepicker/build/js/bootstrap-datetimepicker.min.js',  # NOQA
        'jquery-textcomplete/dist/jquery.textcomplete.min.js',
        'emojione/lib/js/emojione.min.js',
        'emojionearea/dist/emojionearea.min.js',
        # amcharts files
        'js/amcharts.js',
        'js/serial.js',
        'js/pie.js',
        'js/plugins/export/export.min.js',
        'js/themes/light.js',
        # amcharts libs for export
        'js/plugins/export/libs/pdfmake/pdfmake.min.js',
        'js/plugins/export/libs/pdfmake/vfs_fonts.js',
        'js/plugins/export/libs/jszip/jszip.min.js',
        'js/plugins/export/libs/fabric.js/fabric.min.js',
        'js/plugins/export/libs/FileSaver.js/FileSaver.min.js',
        'main.js',
    )

    js_bulletin_edit = Bundle(
        js_main,
        'bulletin-edit.js'
    )

    js_story_edit = Bundle(
        js_main,
        'story-edit.js'
    )

    css_landing = Bundle(
        'landing.css',
        'emojione/assets/css/emojione.min.css',
    )

    js_landing = Bundle(
        'jquery/dist/jquery.min.js',
        'hamburger.menu.js',
        'typed.js/lib/typed.min.js',
    )

    assets.register('css_main', css_main, output='dist/css/main.css')
    assets.register('js_main', js_main, output='dist/js/main.js')

    assets.register('js_bulletin_edit', js_bulletin_edit,
                    output='dist/js/bulletin-edit.js')

    assets.register('js_story_edit', js_story_edit,
                    output='dist/js/story-edit.js')

    assets.register('css_landing', css_landing, output='dist/css/landing.css')
    assets.register('js_landing', js_landing, output='dist/js/landing.js')
