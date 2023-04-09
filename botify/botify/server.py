import json
import logging
import time
from dataclasses import asdict
from datetime import datetime

from flask import Flask
from flask_redis import Redis
from flask_restful import Resource, Api, abort, reqparse
from gevent.pywsgi import WSGIServer

from botify.data import DataLogger, Datum
from botify.experiment import Experiments, Treatment
from botify.recommenders.random import Random
from botify.recommenders.sticky_artist import StickyArtist
from botify.recommenders.toppop import TopPop
from botify.recommenders.indexed import Indexed
from botify.recommenders.contextual import Contextual
from botify.track import Catalog

import numpy as np

root = logging.getLogger()
root.setLevel("INFO")

app = Flask(__name__)
app.config.from_file("config.json", load=json.load)
api = Api(app)

# TODO Seminar 6 step 3: Create redis DB with tracks with diverse recommendations
tracks_redis = Redis(app, config_prefix="REDIS_TRACKS")
tracks_with_diverse_recs_redis = Redis(app, config_prefix="REDIS_TRACKS_WITH_DIVERSE_RECS")
# seminar 2: create a redis db for artists' tracks
artists_redis = Redis(app, config_prefix="REDIS_ARTIST")  # prefix from config.json
recommendations_redis = Redis(app, config_prefix="REDIS_RECOMMENDATIONS")
recommendations_ub_redis = Redis(app, config_prefix="REDIS_RECOMMENDATIONS_UB")

data_logger = DataLogger(app)

# TODO Seminar 6 step 4: Upload tracks with diverse recommendations to redis DB
catalog = Catalog(app).load(
    app.config["TRACKS_CATALOG"],
    app.config["TOP_TRACKS_CATALOG"],  # seminar 3: передаем топ треков
    app.config["TRACKS_WITH_DIVERSE_RECS_CATALOG"]
)
catalog.upload_tracks(tracks_redis.connection, tracks_with_diverse_recs_redis.connection)
# seminar 2: загрузим исполнителей
catalog.upload_artists(artists_redis.connection)  # передаем БД, созданную в track.upload_artists
catalog.upload_recommendations(recommendations_redis.connection)
catalog.upload_recommendations(recommendations_ub_redis.connection, "RECOMMENDATIONS_UB_FILE_PATH")

parser = reqparse.RequestParser()
parser.add_argument("track", type=int, location="json", required=True)
parser.add_argument("time", type=float, location="json", required=True)


class Hello(Resource):
    def get(self):
        return {
            "status": "alive",
            "message": "welcome to botify, the best toy music recommender",
        }


class Track(Resource):
    def get(self, track: int):
        data = tracks_redis.connection.get(track)
        if data is not None:
            return asdict(catalog.from_bytes(data))
        else:
            abort(404, description="Track not found")


class NextTrack(Resource):
    def post(self, user: int):
        start = time.time()

        args = parser.parse_args()

        # TODO Seminar 6 step 6: Wire RECOMMENDERS A/B experiment
        # вызываем созданный нами эксперимент!
        treatment = Experiments.RECOMMENDERS.assign(user)
        # делим пользователей на группы
        if treatment == Treatment.T1:
            # seminar 2 (02.22)
            recommender = StickyArtist(tracks_redis.connection, artists_redis.connection, catalog)
        elif treatment == Treatment.T2:
            # seminar 3
            # топ-100 - лучше, чем для топ-10 и топ-1000 (проверили на семинаре)
            recommender = TopPop(tracks_redis.connection, catalog.top_tracks[:100])
        elif treatment == Treatment.T3:
            # seminar 4: --episodes 2000 multi --processes 2
            # user-based, где не для каждого юзера есть рекомендации (ИСПОЛЬЗУЕТСЯ РЕДКО!)
            recommender = Indexed(tracks_redis.connection, recommendations_ub_redis.connection, catalog)
        elif treatment == Treatment.T4:
            # seminar 5: --episodes 2000 multi --processes 2
            # тот же рекомендер, что на серимнаре 4, только поменяли путь к файлу
            recommender = Indexed(tracks_redis.connection, recommendations_redis.connection, catalog)
        # TODO: ТУТ ПОЯВИЛАСЬ ДОМАШКА (22.03.23 у нас 30.03.23)
        # предложить рекоммендер, который побьет самый лучший рекоммендер с семинара
        # пул-реквест в репозиторий
        # отчет + сравнение с помощью первого блокнота (победа по ключевой метрике)
        # Комментарий: можно брать за основу решение с light-fm, но так могут сделать многие
        elif treatment == Treatment.T5:
            # Seminar 6
            # К какому подходу относится? Коллаборативный или конткнтный?
            # Ответ: Что-то среднее:)
            # т.к. в процессе обучения учимся по времени, которое оставляет пользователь,
            # а предсказываем рекомендации для треков!
            recommender = Contextual(tracks_redis.connection, catalog)
        elif treatment == Treatment.T6:
            recommender = Contextual(tracks_with_diverse_recs_redis.connection, catalog)
        else:
            recommender = Random(tracks_redis.connection)  # контроль-группа

        recommendation = recommender.recommend_next(user, args.track, args.time)

        data_logger.log(
            "next",
            Datum(
                int(datetime.now().timestamp() * 1000),
                user,
                args.track,
                args.time,
                time.time() - start,
                recommendation,
            ),
        )
        return {"user": user, "track": recommendation}


class LastTrack(Resource):
    def post(self, user: int):
        start = time.time()
        args = parser.parse_args()
        data_logger.log(
            "last",
            Datum(
                int(datetime.now().timestamp() * 1000),
                user,
                args.track,
                args.time,
                time.time() - start,
            ),
        )
        return {"user": user}


api.add_resource(Hello, "/")
api.add_resource(Track, "/track/<int:track>")
api.add_resource(NextTrack, "/next/<int:user>")
api.add_resource(LastTrack, "/last/<int:user>")


if __name__ == "__main__":
    http_server = WSGIServer(("", 5000), app)
    http_server.serve_forever()
