# -*- coding: utf-8 -*-
import logging
import re
from marvinbot.filters import RegexpFilter
from marvinbot.handlers import CommandHandler, MessageHandler
from marvinbot.models import User
from marvinbot.plugins import Plugin
from marvinbot.utils import trim_markdown
from save_plugin.models import ChatLink

log = logging.getLogger(__name__)


class SavePlugin(Plugin):
    def __init__(self):
        super(SavePlugin, self).__init__('save_plugin')

    def get_default_config(self):
        return {
            'short_name': self.name,
            'default_target_chat_id': None,
            'enabled': True,
        }

    def configure(self, config):
        self.config = config
        if self.config.get('default_target_chat_id', None) is None:
            log.warn(
                'Key default_target_chat_id not set in settings. Saving unlinked chats disabled.')

    @staticmethod
    def filter_migrate_chat(message):
        return message.migrate_to_chat_id is not None

    def setup_handlers(self, adapter):
        self.add_handler(CommandHandler('save', self.on_save_command,
                                        command_description='Save a message or configure saving for this chat.')
                         .add_argument('--link', help='Link this chat to save messages to another.',
                                       action='store_true')
                         .add_argument('--unlink', help='Unlink this chat.', action='store_true')
                         .add_argument('code', nargs='*', help='Code'))
        self.add_handler(MessageHandler(RegexpFilter(
            r'sa+v+e+d*\b', flags=re.IGNORECASE), self.on_save_message))
        self.add_handler(MessageHandler(
            [SavePlugin.filter_migrate_chat], SavePlugin.on_chat_migrated, strict=True))

    def setup_schedules(self, adapter):
        pass

    @staticmethod
    def on_chat_migrated(update):
        migrate_to_chat_id = update.effective_message.migrate_to_chat_id
        migrate_from_chat_id = update.effective_message.chat.id

        # Migrate all chat links with source chat id equal to migrate_from_chat_id
        migrations = 0
        chat_link = ChatLink.by_source_chat_id(migrate_from_chat_id)
        if chat_link:
            migrations = 1
            chat_link.source_chat_id = migrate_to_chat_id
            chat_link.save()

        # Migrate all chat links with target chat id equal to migrate_from_chat_id
        for chat_link in ChatLink.all_by_target_chat_id(migrate_from_chat_id):
            migrations = migrations + 1
            chat_link.target_chat_id = migrate_to_chat_id
            chat_link.save()

        log.info('Migrated {} chat from {} to {}'.format(
            migrations, migrate_from_chat_id, migrate_to_chat_id))

    def on_save_message(self, update):
        message = update.effective_message
        chat_id = message.chat.id

        if message.reply_to_message is None:
            # message.reply_text(text='❌ You must say save when replying.')
            return

        chat_link = ChatLink.by_source_chat_id(chat_id)

        if chat_link is None or chat_link.target_chat_id is None:
            target_chat_id = self.config.get('default_target_chat_id', None)
        else:
            target_chat_id = chat_link.target_chat_id

        if target_chat_id is None:
            return

        self.do_save_message(target_chat_id, message)

    def do_save_message(self, target_chat_id, message):
        target_chat = self.adapter.bot.getChat(target_chat_id)

        message.reply_to_message.forward(target_chat_id)
        target_chat.send_message(text='Saved by {name} from {title}'.format(
            name=message.from_user.mention_markdown(),
            title=trim_markdown(
                message.chat.title or message.chat.first_name)
        ),
            parse_mode='Markdown',
            disable_web_page_preview=True,
            disable_notification=True)

        if target_chat.username:
            message.reply_text(text='✅ Saved to [{title}](https://t.me/{username}) ({type}).'.format(
                title=trim_markdown(
                    target_chat.title or target_chat.first_name),
                username=target_chat.username,
                type=target_chat.type),
                parse_mode='Markdown',
                disable_web_page_preview=True,
                disable_notification=True)
        else:
            message.reply_text(text='✅ Saved to {title} ({type}).'.format(
                title=trim_markdown(target_chat.title or target_chat.first_name), type=target_chat.type))

    def on_save_command(self, update, link=False, unlink=False, code=[]):
        message = update.effective_message
        chat_id = message.chat.id
        code_str = ' '.join([fragment.strip() for fragment in code])

        if message.reply_to_message:
            chat_link = ChatLink.by_source_chat_id(chat_id)

            if chat_link is None or chat_link.target_chat_id is None:
                target_chat_id = self.config.get(
                    'default_target_chat_id', None)
            else:
                target_chat_id = chat_link.target_chat_id

            if target_chat_id is None:
                return

            self.do_save_message(target_chat_id, message)
            return

        if not User.is_user_admin(message.from_user):
            message.reply_text(text='❌ You must be an admin to do that.')
            return

        if link:
            chat_link = ChatLink.by_source_chat_id(chat_id)

            if chat_link is None:
                chat_link = ChatLink(
                    source_chat_id=chat_id,
                    target_chat_id=None,
                    first_name=message.from_user.first_name,
                    user_id=message.from_user.id
                )
                chat_link.save()

            if chat_link.target_chat_id:
                message.reply_text(text='⚠ This chat is already linked.')
                return

            message.reply_text(
                text='⚠️ Invite me to the chat were you want messages to be saved and run the following command there:\n/save {}'.format(
                    chat_link.id))
            return

        if unlink:
            chat_link = ChatLink.by_source_chat_id(chat_id)
            if chat_link is None:
                message.reply_text(text='❌ Chat is not linked.')
                return

            chat_link.delete()
            message.reply_text(text='🚮 Chat unlinked.')
            return

        if len(code_str):
            chat_linkByCode = ChatLink.by_id(code_str)
            if chat_linkByCode is None:
                message.reply_text(text='❌ You must provide a valid code.')
                return
            elif chat_id == chat_linkByCode.source_chat_id:
                message.reply_text(
                    text='❌ You must run this command in a different chat.')
                return
            elif chat_linkByCode.target_chat_id:
                message.reply_text(
                    text='❌ You must provide a code that is not used.')
                return

            chat_linkByCode.target_chat_id = chat_id
            chat_linkByCode.save()
            message.reply_text(text='✅ Chats linked.')
            return
