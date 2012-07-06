from datetime import datetime
from threading import Timer
from config import CHATROOM_PRESENCE
from errbot.botplugin import BotPlugin
from feedparser import parse
from errbot.jabberbot import botcmd

__author__ = 'atalyad'


def get_item_date(rss_item):
    return datetime(rss_item.published_parsed.tm_year,
                        rss_item.published_parsed.tm_mon,
                        rss_item.published_parsed.tm_mday,
                        rss_item.published_parsed.tm_hour,
                        rss_item.published_parsed.tm_min,
                        rss_item.published_parsed.tm_sec)


class RSSFeedPlugin(BotPlugin):

    min_err_version = '1.3.0' # it needs the configuration feature and split_args_with=

    def get_configuration_template(self):
        return {'POLL_INTERVAL' : 1800.0}

    def configure(self, configuration):
        if configuration:
            if type(configuration) != dict:
                super(RSSFeedPlugin, self).configure(None)
                raise Exception('Wrong configuration type')

            if not configuration.has_key('POLL_INTERVAL'):
                super(RSSFeedPlugin, self).configure(None)
                raise Exception('Wrong configuration type, it should contain POLL_INTERVAL')
            if len(configuration) > 1:
                super(RSSFeedPlugin, self).configure(None)
                raise Exception('What else did you try to insert in my config ?')
            try:
                float(configuration['POLL_INTERVAL'])
            except:
                super(RSSFeedPlugin, self).configure(None)
                raise Exception('POLL_INTERVAL must be a float')
        super(RSSFeedPlugin, self).configure(configuration)


    def get_subscriptions_last_ts(self):
        return self.get('subscriptions_last_ts', {})

    def get_subscription_names(self):
        return self.get('subscription_names', {})

    def add_subscription(self, url, name):
        subscriptions = self.get_subscription_names()
        subscriptions[name] = url
        tss = self.get_subscriptions_last_ts()
        tss[name] = datetime.min
        self['subscription_names'] = subscriptions
        self['subscriptions_last_ts'] = tss


    def remove_subscription(self, name):
        subscriptions = self.get_subscription_names()
        tss = self.get_subscriptions_last_ts()
        del subscriptions[name]
        del tss[name]
        self['subscription_names'] = subscriptions
        self['subscriptions_last_ts'] = tss


    def send_news(self):

        """
        Go through RSS subscriptions, check if there's a new update and send it to the chat.
        """
        subscription_names = self.get_subscription_names()
        subscription_tss = self.get_subscriptions_last_ts()
        for name in subscription_names:
            if subscription_tss[name] < datetime.now():
                feed = parse(subscription_names[name])
                if feed['entries']:
                    item = feed['entries'][0]
                    item_date = get_item_date(item)
                    if item_date > subscription_tss[name]:
                        subscription_tss[name] = item_date
                        msg = '%s News from %s:\n%s' % (str(item_date), str(name), str(item.summary))
                        self.send(CHATROOM_PRESENCE[0], msg)
                        self.send(CHATROOM_PRESENCE[0], str(item.link))

                        self['subscriptions_last_ts'] = subscription_tss
                        self.shelf.sync()

        if not self.config:
            poll_interval = 1800.0
        else:
            poll_interval = float(self.config.get('POLL_INTERVAL', 1800.0))


        self.t = Timer(poll_interval, self.send_news)
        self.t.setDaemon(True) # so it is not locking on exit
        self.t.start()


    def callback_connect(self):
        if not self.config:
            self.send(CHATROOM_PRESENCE[0], 'This plugin can be configured. Default polling interval is 1800.0 seconds. To modify run !config RSSFeedPlugin')
        self.send_news()


    @botcmd(split_args_with=' ')
    def rss_add(self, mess, args):
        """
        Add a feed: !rss add feed_url feed_nickname
        """
        if len(args) < 2:
            return 'Please supply a feed url and a nickname'

        feed_url = args[0].strip()

        feed_name = ''
        for i in range(1, len(args)):
            feed_name += args[i] + ' '
        feed_name = feed_name.strip()

        if feed_name in self.get_subscription_names():
            return 'this feed already exists'
        self.add_subscription(feed_url, feed_name)
        self.shelf.sync()
        return 'Feed %s added as %s' % (feed_url, feed_name)


    @botcmd
    def rss_remove(self, mess, args):
        """
        Remove a feed: !rss remove feed_nickname
        """
        if not args:
            return 'Please supply a feed nickname'
        feed_name = args.strip()
        if feed_name not in self.get_subscription_names():
            return 'Sorry.. unknown feed...'
        self.remove_subscription(feed_name)
        self.shelf.sync()
        return 'Feed %s was successfully removed.' % feed_name


    @botcmd(split_args_with=' ')
    def rss_feeds(self, mess, args):
        """
        Display all active feeds with last update date
        """
        ans = ''
        for sub_name in self.get_subscriptions_last_ts():
            ans += '%s  last updated: %s (from %s)\n' % (sub_name, self.get_subscriptions_last_ts()[sub_name], self.get_subscription_names()[sub_name])

        return ans


    @botcmd(admin_only = True, split_args_with=' ')
    def rss_clearfeeds(self, mess, args):
        """ WARNING : Deletes all existing feeds
        """
        self['subscription_names'] = {}
        self['subscriptions_last_ts'] = {}
        self.shelf.sync()
        return 'all rss feeds were removed'
