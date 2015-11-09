from django.conf import settings

if settings.SURROUND_SENTRY_ENABLE:
    import raven
    def get_sentry_client():
        return raven.Client(settings.RAVEN_CONFIG['dsn'])

    def call(name, *args, **kwargs):
        return getattr(get_sentry_client(), name)(*args, **kwargs)

else:
    def get_sentry_client():
        return None

    def call(name, *args, **kwargs):
        pass

