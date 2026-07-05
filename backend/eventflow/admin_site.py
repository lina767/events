"""
Orders the Django admin's app index by hand instead of the default
alphabetical sort, so each app reads as a main resource followed by its
supporting sub-resources (e.g. People -> Duplicates -> Merge log) rather
than being scattered by model name.
"""

from django.contrib import admin

MODEL_ORDER = {
    "people": ["Person", "DuplicateCandidate", "PersonMergeLog"],
}

_default_get_app_list = admin.AdminSite.get_app_list


def _ordered_get_app_list(self, request, app_label=None):
    app_list = _default_get_app_list(self, request, app_label=app_label)
    for app in app_list:
        order = MODEL_ORDER.get(app["app_label"])
        if not order:
            continue
        app["models"].sort(
            key=lambda m: order.index(m["object_name"]) if m["object_name"] in order else len(order)
        )
    return app_list


admin.AdminSite.get_app_list = _ordered_get_app_list
