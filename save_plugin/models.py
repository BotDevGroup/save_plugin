import mongoengine
from marvinbot.utils import localized_date


class ChatLink(mongoengine.Document):

    source_chat_id = mongoengine.LongField(required=True, null=False)
    target_chat_id = mongoengine.LongField(null=True)
    first_name = mongoengine.StringField()
    user_id = mongoengine.LongField(required=True, null=False)

    date_added = mongoengine.DateTimeField(default=localized_date)

    @classmethod
    def all_by_source_chat_id(cls, id):
        try:
            return cls.objects.filter(source_chat_id=id)
        except:
            return []

    @classmethod
    def all_by_target_chat_id(cls, id):
        try:
            return cls.objects.filter(target_chat_id=id)
        except:
            return []

    @classmethod
    def by_id(cls, id):
        try:
            return cls.objects.get(id=id)
        except:
            return None

    @classmethod
    def by_source_chat_id(cls, id):
        try:
            return cls.objects.get(source_chat_id=id)
        except:
            return None

    def __str__(self):
        return "{{ id = \"{id}\", source_chat_id = {source_chat_id}, target_chat_id = {target_chat_id} }}".format(
            id=self.id,
            source_chat_id=self.source_chat_id,
            target_chat_id=self.target_chat_id)
