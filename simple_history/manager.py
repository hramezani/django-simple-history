from __future__ import unicode_literals

from django.db import models


class HistoryDescriptor(object):
    def __init__(self, model):
        self.model = model

    def __get__(self, instance, owner):
        if instance is None:
            return HistoryManager(self.model)
        return HistoryManager(self.model, instance)


class HistoryManager(models.Manager):
    def __init__(self, model, instance=None):
        super(HistoryManager, self).__init__()
        self.model = model
        self.instance = instance

    def get_super_queryset(self):
        try:
            return super(HistoryManager, self).get_queryset()
        except AttributeError:
            return super(HistoryManager, self).get_query_set()

    def get_queryset(self):
        qs = self.get_super_queryset()
        if self.instance is None:
            return qs

        if isinstance(self.instance._meta.pk, models.OneToOneField):
            filter = {self.instance._meta.pk.name + "_id": self.instance.pk}
        else:
            filter = {self.instance._meta.pk.name: self.instance.pk}
        return self.get_super_queryset().filter(**filter)

    get_query_set = get_queryset

    def most_recent(self):
        """
        Returns the most recent copy of the instance available in the history.
        """
        if not self.instance:
            raise TypeError("Can't use most_recent() without a %s instance." %
                            self.model._meta.object_name)
        tmp = []
        for field in self.instance._meta.fields:
            if isinstance(field, models.ForeignKey):
                tmp.append(field.name + "_id")
            else:
                tmp.append(field.name)
        fields = tuple(tmp)
        try:
            values = self.values_list(*fields)[0]
        except IndexError:
            raise self.instance.DoesNotExist("%s has no historical record." %
                                             self.instance._meta.object_name)
        return self.instance.__class__(*values)

    def as_of(self, date):
        """
        Returns an instance, or an iterable of the instances, of the
        original model with all the attributes set according to what
        was present on the object on the date provided.
        """
        queryset = self.filter(history_date__lte=date)
        if self.instance:
            try:
                history_obj = queryset[0]
            except IndexError:
                raise self.instance.DoesNotExist(
                    "%s had not yet been created." %
                    self.instance._meta.object_name)
            if history_obj.history_type == '-':
                raise self.instance.DoesNotExist(
                    "%s had already been deleted." %
                    self.instance._meta.object_name)
            return history_obj.instance
        historical_ids = set(
            queryset.order_by().values_list('id', flat=True))
        return (change.instance for change in (
            queryset.filter(id=original_pk).latest('history_date')
            for original_pk in historical_ids
        ) if change.history_type != '-')
