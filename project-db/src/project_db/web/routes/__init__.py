"""Route modules.  Each one registers a small surface area on the app
factory in ``project_db.web.app.create_app``.

Routes are deliberately *thin* -- they pull data from
``project_db.web.ui_views`` and hand it to a template.  No derived logic
lives in this package.
"""
