import sys
from typing import Any
import re
from base64 import b64encode, b64decode
from collections import OrderedDict
from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Signature import PKCS1_v1_5
from json import JSONDecodeError
from urllib.parse import urljoin, quote_plus

from . import conf
from .exceptions import CsobBaseException, CsobJSONDecodeError, CsobVerifyError
from requests.exceptions import HTTPError


try:
    from django.utils import timezone as datetime
except ImportError:
    from datetime import datetime


def sign(payload, key):
    msg = mk_msg_for_sign(payload)
    h = SHA256.new(msg)
    signer = PKCS1_v1_5.new(RSA.importKey(key))
    return b64encode(signer.sign(h)).decode()


def verify(payload, signature, pubkey):
    msg = mk_msg_for_sign(payload)
    key = RSA.importKey(pubkey)
    h = SHA256.new(msg)
    verifier = PKCS1_v1_5.new(key)
    return verifier.verify(h, b64decode(signature))


def mk_msg_for_sign(payload):
    payload = {k: v for k, v in payload.items() if v is not None}
    if 'cart' in payload and payload['cart'] not in conf.EMPTY_VALUES:
        cart_msg = []
        for one in payload['cart']:
            cart_msg.extend(one.values())
        payload['cart'] = '|'.join(map(str_or_jsbool, cart_msg))
    msg = '|'.join(map(str_or_jsbool, payload.values()))
    return msg.encode('utf-8')


def mk_payload(key, pairs):
    payload = OrderedDict([(k, v) for k, v in pairs if v not in conf.EMPTY_VALUES])
    payload['signature'] = sign(payload, key)
    return payload


def mk_url(base_url, endpoint_url, payload=None):
    url = urljoin(base_url, endpoint_url)
    if payload is None:
        return url
    return urljoin(url, '/'.join(map(quote_plus, payload.values())))


def str_or_jsbool(v):
    if type(v) == bool:
        return str(v).lower()
    return str(v)


def dttm(format_='%Y%m%d%H%M%S'):
    return datetime.now().strftime(format_)


def validate_response(response, key):
    try:
        response.raise_for_status()
        data = response.json()
    except JSONDecodeError:
        raise CsobJSONDecodeError('Cannot decode JSON in response')
    except HTTPError as raised_exception:
        raise CsobBaseException(raised_exception)

    signature = data.pop('signature')
    payload = OrderedDict()

    for k in conf.RESPONSE_KEYS:
        if k in data:
            payload[k] = data[k]

    if not verify(payload, signature, key):
        raise CsobVerifyError('Cannot verify response')

    response.extensions = []
    response.payload = payload

    # extensions
    if 'extensions' in data:
        maskclnrp_keys = 'extension', 'dttm', 'maskedCln', 'expiration', 'longMaskedCln'
        for one in data['extensions']:
            if one['extension'] in ('maskClnRP', 'maskCln'):
                o = OrderedDict()
                for k in maskclnrp_keys:
                    if k in one:
                        o[k] = one[k]
                if verify(o, one['signature'], key):
                    response.extensions.append(o)
                else:
                    raise CsobVerifyError('Cannot verify masked card extension response')

    return response


PROVIDERS = (
    (conf.CARD_PROVIDER_VISA, re.compile(r'^4\d{5}$')),
    (conf.CARD_PROVIDER_AMEX, re.compile(r'^3[47]\d{4}$')),
    (conf.CARD_PROVIDER_DINERS, re.compile(r'^3(?:0[0-5]|[68][0-9])[0-9]{4}$')),
    (conf.CARD_PROVIDER_JCB, re.compile(r'^(?:2131|1800|35[0-9]{2})[0-9]{2}$')),
    (conf.CARD_PROVIDER_MC, re.compile(r'^5[1-5][0-9]{4}|222[1-9][0-9]{2}|22[3-9][0-9]{4}|2[3-6][0-9]{5}|27[01][0-9]{4}|2720[0-9]{2}$')),
)


def get_card_provider(long_masked_number):
    for provider_id, rx in PROVIDERS:
        if rx.match(long_masked_number[:6]):
            return provider_id, conf.CARD_PROVIDERS[provider_id]
    return None, None


def to_camel_case(value):
    """
    If the value is not None, convert the value from snake_case to camelCase format. If the value is not in snake_case
    format, return the original value.
    """

    if value is None:
        return value

    first_word, *other_words = value.split('_')
    return "".join([first_word.lower(), *map(str.title, other_words)]) if other_words else first_word


def convert_keys_to_camel_case(data):
    """
    Convert all dictionary keys and nested dictionary keys from snake_case to camelCase format.
    """

    if not data:
        return data
    if isinstance(data, list):
        return [convert_keys_to_camel_case(value) if isinstance(value, (dict, list)) else value for value in data]
    return {
       to_camel_case(key): convert_keys_to_camel_case(value) if isinstance(value, (dict, list)) else value
       for key, value in data.items()
    }
