import random
from typing import List

from .random import Random
from .recommender import Recommender


class TopPop(Recommender):
    """
    Seminar 3
    """
    def __init__(self, tracks_redis, top_tracks: List[int]):
        self.random = Random(tracks_redis)
        self.top_tracks = top_tracks  # топ треков из файла (топ-10 или топ-100)

    def recommend_next(self, user: int, prev_track: int, prev_track_time: float) -> int:
        if self.top_tracks:
            shuffled = list(self.top_tracks)
            random.shuffle(shuffled)
            return shuffled[0]  # возвращаем случайный трек из топа

        return self.random.recommend_next(user, prev_track, prev_track_time)
