`app.main:app --reload`


`celery -A app.celery_worker.celery_app worker --loglevel=info --pool=solo`
