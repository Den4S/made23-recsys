import random
from typing import List, Dict

from .random import Random
from .recommender import Recommender
from .indexed import Indexed  # tracks_redis.connection, recommendations_redis.connection, catalog
from .toppop import TopPop  # tracks_redis.connection, catalog.top_tracks[:100]
import random


class Weighted(Recommender):
    """
    Homework
    1. combine predictions of several recommenders with top-3 best results in mean_time_per_session
        - Contextual
        - Indexed
        - TopPop
    2. count reccomendations from each of them with different weights!
    3. store users history: likes and dislikes
    4. store our previous recommendation
    """

    def __init__(self,
                 tracks_redis,
                 recommendations_redis,  # for Indexed
                 catalog,
                 users_likes: Dict[int, List[int]],
                 users_dislikes: Dict[int, List[int]],
                 users_current_recs):  # current recs for eac user List[int, Iterator[int]]
        self.tracks_redis = tracks_redis
        self.recommendations_redis = recommendations_redis
        self.fallback = Random(tracks_redis)
        self.catalog = catalog
        self.top = 100  # size of top
        # models weights
        self.nn_weight = 2  # weight for NN recommendations
        self.ind_weight = 1.25  # weight for Indexed recommendations
        self.top_weight = 0.75  # weight for TopPop recommendations
        # the time threshold to understand if the user liked (res>=TH) the track or not (res<TH)
        self.good_threshold = 0.75
        # numder of tracks in one recommendation
        self.n_recommended = 25
        # users history
        self.users_likes = users_likes  # value: list of all liked tracks id
        self.users_dislikes = users_dislikes  # value: list of all disliked tracks id
        self.users_current_recs = users_current_recs

    def liked_prev_track(self, user: int, prev_track: int):
        """
        To do if the last track was good
        """
        if user in self.users_likes.keys():  # if the key exists
            if prev_track in self.users_likes[user]:
                self.users_likes[user].remove(prev_track)
            self.users_likes[user].append(prev_track)  # add to likes (at the end!)
        else:
            self.users_likes[user] = [prev_track]  # create first elem in likes
        if user in self.users_dislikes.keys():  # if dislikes exists for the user
            if prev_track in self.users_dislikes[user]:
                self.users_dislikes[user].remove(prev_track)  # if track was previously disliked -- remove from dislikes

    def disliked_prev_track(self, user: int, prev_track: int):
        """
        To do if the last track was bad
        """
        if user in self.users_dislikes.keys():
            if prev_track not in self.users_dislikes[user]:  # if track was already disliked
                self.users_dislikes[user].append(prev_track)  # add it to dislikes (order doesn't matter)
        else:
            self.users_dislikes[user] = [prev_track]  # create first elem in dislikes
        if user in self.users_likes.keys():  # if likes exists
            if prev_track in self.users_likes[user]:
                self.users_likes[user].remove(prev_track)  # if track was previously disliked -- remove from dislikes

    def check_dislike(self, user: int, track: int):
        """
        Returns True if the user is already disliked the track
        """
        if user in self.users_dislikes.keys():
            if track in self.users_dislikes[user]:
                return True
        return False

    def get_contextual_recommendations(self, prev_track: int) -> List[int]:
        previous_track = self.tracks_redis.get(prev_track)  # get the previous track
        if previous_track is None:  # no track - no recommendations
            return list()
        previous_track = self.catalog.from_bytes(previous_track)
        recommendations = previous_track.recommendations  # contextual recommendations
        if recommendations:
            return list(recommendations)
        return list()

    def get_indexed_recommendations(self, user: int) -> List[int]:
        recommendations = self.recommendations_redis.get(user)  # get user's recommendations from redis
        if recommendations:
            return list(self.catalog.from_bytes(recommendations))
        return list()

    def get_top(self, user: int) -> List[int]:
        if self.catalog.top_tracks[:self.top]:
            return list(self.catalog.top_tracks[:self.top])
        return self.get_random(user)

    def get_random(self, user: int) -> List[int]:
        rnd_recs = []
        while len(rnd_recs) < self.n_recommended:
            new_rnd = int(self.tracks_redis.randomkey())  # random track
            if new_rnd not in rnd_recs:  # no duplicates
                if self.check_dislike(user, new_rnd):  # if track is disliked by user
                    continue  # not recommend already disliked tracks
                rnd_recs.append(new_rnd)
        return rnd_recs

    def prepare_recommendations(self, user: int, prev_liked_track: int) -> List[int]:
        """
        Compute a weighted recommendations!
        """
        nn_recs = self.get_contextual_recommendations(prev_liked_track)
        ind_recs = self.get_indexed_recommendations(user)
        top_recs = self.get_top(user)

        unique_tracks = list(set().union(*[nn_recs, ind_recs, top_recs]))
        unique_tracks_not_disliked = []
        for track in unique_tracks:
            if not self.check_dislike(user, track):
                unique_tracks_not_disliked.append(track)  # count only not disliked tracks
        tracks_weights = [0 for _ in range(len(unique_tracks_not_disliked))]
        for ind, track in enumerate(unique_tracks_not_disliked):  # count recommended tracks weights
            if track in nn_recs:
                tracks_weights[ind] += self.nn_weight
            if track in ind_recs:
                tracks_weights[ind] += self.ind_weight
            if track in top_recs:
                tracks_weights[ind] += self.top_weight
        # now lets sort tracks in the descending order by their weights!
        sorted_recs = [track for _, track in sorted(zip(tracks_weights, unique_tracks_not_disliked), reverse=True)]
        if len(sorted_recs) > 0:
            if len(sorted_recs) >= self.n_recommended:
                return sorted_recs[:self.n_recommended]
            return sorted_recs
        else:  # if empty recs
            return self.get_random(user)

    def update_user_recs(self, user: int, prev_liked_track: int):
        new_user_recs = self.prepare_recommendations(user, prev_liked_track)
        self.users_current_recs[user] = iter(new_user_recs)  # add new recommendations to user (ITERATOR!)

    def recommend_one_from_top(self, user: int) -> int:
        top_recs = self.get_top(user)
        shuffled_top = top_recs
        random.shuffle(shuffled_top)
        shuffeled_top_iter = iter(shuffled_top)
        not_found = True
        while not_found:
            next_track = next(shuffeled_top_iter)
            if self.check_dislike(user, next_track):  # if track is disliked by user
                continue
            not_found = False
        return next_track

    def recommend_next(self, user: int, prev_track: int, prev_track_time: float) -> int:
        # check if the previous track was good or not
        if prev_track_time >= self.good_threshold:
            self.liked_prev_track(user, prev_track)  # add like
            if user in self.users_current_recs.keys():  # check if we have prepared recs for user
                try:
                    next_track = next(self.users_current_recs[user])
                except StopIteration:  # need to prepare new recommendations
                    self.update_user_recs(user, prev_track)
                    next_track = next(self.users_current_recs[user])
            else:  # no prepared recs
                self.update_user_recs(user, prev_track)
                next_track = next(self.users_current_recs[user])
        else:  # the previous track was bad
            self.disliked_prev_track(user, prev_track)  # add dislike
            # we need to prepare new recommendations based on the last liked track
            last_liked_track = None
            if user in self.users_likes.keys():
                if self.users_likes[user]:  # if likes is not empty
                    last_liked_track = self.users_likes[user][-1]
            if last_liked_track is None:
                # if there is no liked tracks
                # recommend something from TOP
                next_track = self.recommend_one_from_top(user)
            else:
                self.update_user_recs(user, last_liked_track)
                next_track = next(self.users_current_recs[user])
        return next_track
