from enum import Enum


class EndpointUrl(Enum):
    CUSTOMER_INFO = 'customer/info/'
    ECHO = 'echo/'
    ONE_CLICK_INIT = 'oneclick/init/'
    ONE_CLICK_PROCESS = 'oneclick/process/'
    PAYMENT_CLOSE = 'payment/close/'
    PAYMENT_INIT = 'payment/init/'
    PAYMENT_PROCESS = 'payment/process/'
    PAYMENT_REFUND = 'payment/refund/'
    PAYMENT_REVERSE = 'payment/reverse/'
    PAYMENT_STATUS = 'payment/status/'
