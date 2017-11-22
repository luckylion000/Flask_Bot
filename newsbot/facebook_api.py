
import json
from urllib.parse import urlencode

import requests


class FacebookAPIError(Exception):
    pass


class FacebookAPI:

    GRAPH_URL = 'https://graph.facebook.com/v2.8'

    def __init__(self, access_token):
        self.access_token = access_token
        self.params = {'access_token': self.access_token}

    def __process_response(self, response):

        if response.status_code != 200:
            raise FacebookAPIError(response.json())

        return response.json()

    def get_user(self, user_id):

        response = requests.get(self.GRAPH_URL + "/%s" % user_id,
                                params=self.params)

        return self.__process_response(response)

    def get_accounts(self):

        response = requests.get(self.GRAPH_URL + '/me/accounts',
                                params=self.params)

        return self.__process_response(response)

    def get_batch_user_and_accounts(self):

        data = {'batch': json.dumps([
                            {'method': 'GET', 'relative_url': 'me'},
                            {'method': 'GET', 'relative_url': 'me/accounts'}
                            ])}

        response = requests.post(self.GRAPH_URL,
                                 params=self.params,
                                 data=data)

        data = self.__process_response(response)

        for b in data:
            if b['code'] != 200:
                raise FacebookAPIError(data)
            b['body'] = json.loads(b['body'])

        return data

    def get_page(self, page_id):

        response = requests.get(self.GRAPH_URL + '/%s' % page_id,
                                params=self.params)

        return self.__process_response(response)

    def subscribed_apps(self):
        response = requests.post(self.GRAPH_URL + '/me/subscribed_apps',
                                 params=self.params)

        return self.__process_response(response)

    def __send_media(self, media_type, recipient_id, url, buttons=None):

        headers = {'Content-Type': 'application/json'}

        json_data = {
            'recipient': {
                'id': recipient_id
            },
            'message': {
                'attachment': {
                    'type': media_type,
                    'payload': {
                        'url': url
                    }
                }
            }
        }

        if buttons:
            buttons = [{'content_type': 'text', 'title': b, 'payload': b} for b in buttons]
            json_data['message']['quick_replies'] = buttons

        response = requests.post(self.GRAPH_URL + '/me/messages',
                                 params=self.params,
                                 headers=headers,
                                 json=json_data)

        return self.__process_response(response)

    def sendAudio(self, recipient_id, url, buttons=None):
        return self.__send_media('audio', recipient_id, url, buttons)

    def sendDocument(self, recipient_id, url, buttons=None):
        return self.__send_media('file', recipient_id, url, buttons)

    def sendPhoto(self, recipient_id, url, buttons=None):
        return self.__send_media('image', recipient_id, url, buttons)

    def sendVideo(self, recipient_id, url, buttons=None):
        return self.__send_media('video', recipient_id, url, buttons)

    def sendMessage(self, recipient_id, message_text, buttons=False):

        headers = {'Content-Type': 'application/json'}

        json_data = {
            'recipient': {
                'id': recipient_id
            },
            'message': {
                'text': message_text,
            }
        }

        if buttons:
            buttons = [{'content_type': 'text', 'title': b, 'payload': b} for b in buttons]
            json_data['message']['quick_replies'] = buttons

        response = requests.post(self.GRAPH_URL + '/me/messages',
                                 params=self.params,
                                 headers=headers,
                                 json=json_data)

        return self.__process_response(response)

    def sendMessagePostback(self, recipient_id, message_text, buttons):

        headers = {'Content-Type': "application/json"}

        buttons = [{'type': 'postback',
                    'title': title,
                    'payload': payload} for (title, payload) in buttons]

        json_data = {
            'recipient': {
                'id': recipient_id
            },
            'message': {
                'attachment': {
                    'type': 'template',
                    'payload': {
                        'template_type': 'button',
                        'text': message_text,
                        'buttons': buttons
                    }
                }
            }
        }

        response = requests.post(self.GRAPH_URL + '/me/messages',
                                 params=self.params,
                                 headers=headers,
                                 json=json_data)

        return self.__process_response(response)


class FacebookAuth:

    GRAPH_URL = 'https://graph.facebook.com/v2.8'

    def __init__(self, app_id, app_secret):
        self.app_id = app_id
        self.app_secret = app_secret

    def get_login_url(self, redirect_uri):

        base_url = 'https://www.facebook.com/v2.8/dialog/oauth'
        return base_url + '?' + urlencode({
            'client_id': self.app_id,
            'redirect_uri': redirect_uri,
            'scope': 'manage_pages,pages_messaging'
        })

    def get_access_token(self, code, redirect_uri):

        params = {
            'client_id': self.app_id,
            'client_secret': self.app_secret,
            'redirect_uri': redirect_uri,
            'code': code
        }

        response = requests.get(self.GRAPH_URL + '/oauth/access_token',
                                params=params)

        if response.status_code != 200:
            raise Exception(response.json())

        return response.json()
