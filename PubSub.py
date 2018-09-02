import argparse
import signal
import time
from threading import Timer

import etcd3
from etcd3 import events
from etcd3.exceptions import ConnectionFailedError, Etcd3Exception


def getArgParser():
    arg_p = argparse.ArgumentParser()
    arg_p.add_argument("-host","--host", default="localhost", type=str, help="Host where etcd is running")
    arg_p.add_argument("-p", "--port", default=2379, type=int, help="Port to connect to etcd")
    pub_sub_parser = arg_p.add_subparsers(title="Actions",
                                          description="allows to publish/subscribe to a key",
                                          dest="action_name")
    sub_parser = pub_sub_parser.add_parser(name="subscribe")
    sub_parser.add_argument("-k", "--key", action="store", default="", type=str, required=True)
    sub_parser.add_argument("-t", "--timeout", action="store", default=0, type=int, required=False)
    pub_parser = pub_sub_parser.add_parser(name="publish")
    pub_parser.add_argument("-k", "--key", action="store", default="", type=str, required=True)
    pub_parser.add_argument("-v", "--value", action="store", default="", type=str, required=True)
    del_parser = pub_sub_parser.add_parser(name="delete")
    del_parser.add_argument("-k", "--key", action="store", default="", type=str, required=True)
    return arg_p


def publisher(etcd3c, pub_key, pub_val="", action="store"):
    """
    Helps to publish the given key/value.
    If action="delete", it removes the key from the key-value store
    :param etcd3c:  etcd3.Etcd3Client
    :param pub_key: string type
    :param pub_val: string type
    :param action: string type. allowed values [store, delete]
    :return: None
    """
    assert isinstance(etcd3c, etcd3.Etcd3Client), "A etcd (version 3) client has to be passed"
    assert isinstance(pub_key, str), "A key for which the changes will be propagated"
    assert isinstance(action, str), "An action to be performed. Currently supported are ['store', 'delete'] "
    action = action.lower()
    if action.startswith("delete") or action.startswith("remove"):
        print "Deletion",
        if etcd3c.delete(pub_key):
            print "success"
        else:
            print "failed"
    else:
        etcd3c.put(pub_key, pub_val)


def subscriber(etcd3C, sub_key, timeout=0):
    """
    helps to subscribe to a key, and watch for specific time (or unlimited)
    if 'timeout' is specified (is greater than ZERO), the subscriber waits for that many seconds.
    Timeout ZERO or less, means unlimited wait.
    :param etcd3C: etcd3.Etcd3Client object
    :param sub_key: key to which it subscribe
    :param timeout: timeout in seconds, if 0 or negative numbers function will wait forever
    :return: None
    """
    assert isinstance(etcd3C, etcd3.Etcd3Client), "A etcd (version 3) client has to be passed"
    assert isinstance(sub_key, str), "A key for which the subscriber listens to"
    assert isinstance(timeout, int), "A timeout for max time it has to wait"
    all_events, cancel_f = etcd3C.watch(sub_key)

    # to handle SIGTERM (Ctrl+C) and SIGINT signals
    # calls the cancel function, 'cancel_f'
    def sig_handler(sig_num, frame):
        cancel_f()

    # adding the signals to be handled
    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)
    # if a timeout is provided, call cancel function after it
    if timeout > 0:
        Timer(timeout, cancel_f).start()
    print "Watching key:", sub_key
    for each_event in all_events:
        if isinstance(each_event, events.PutEvent):
            print "V:", each_event.value + ", added"
        elif isinstance(each_event, events.DeleteEvent):
            print "K:", sub_key + ", deleted"
            cancel_f()
    # sleep is added to mitigate a race condition between
    # python interpreter shutting down and cancel function taking some time to finish
    time.sleep(.5)


def Main():
    arg_p = getArgParser()
    parsed_args = arg_p.parse_args()
    try:
        # instantiate a etcd client (version 3.x api used)
        client3 = etcd3.Etcd3Client(host=parsed_args.host, port=parsed_args.port)
        # check which action command is used
        if parsed_args.action_name == "subscribe":
            subscriber(client3, parsed_args.key, timeout=parsed_args.timeout)
        elif parsed_args.action_name == "publish":
            publisher(client3, parsed_args.key, pub_val=parsed_args.value)
        elif parsed_args.action_name == "delete":
            publisher(client3, parsed_args.key, action=parsed_args.action_name)
    except ConnectionFailedError as ce:
        print "Connection failed: ", ce
    except Etcd3Exception as ee:
        print "Some exception in etcd3 client: ", ee


if __name__ == "__main__":
    Main()
