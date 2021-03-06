from flask import Flask, request, jsonify
from flask_marshmallow import Marshmallow
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
import os
from dotenv import load_dotenv


# app configuration ===================================
app = Flask(__name__)
CORS(app)
db = SQLAlchemy(app)
ma = Marshmallow(app)
load_dotenv()
ENV = 'dev'

if ENV == 'dev':
    app.debug = True
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("MYDB")
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
else:
    app.debug = False
    app.config['SQLALCHEMY_DATABASE_URI'] = ''
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# end of app configuration===========================================


# model creation=============================================
class Movie(db.Model):
    __tablename__ = 'movie'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100))
    query_id = db.Column(db.String(100), unique=True)
    up_count = db.Column(db.Integer)
    down_count = db.Column(db.Integer)
    likes = db.relationship('Like', backref='movie', lazy=True)
    dislikes = db.relationship('Dislike', backref='movie', lazy=True)

    def __init__(self, title, query_id):
        self.title = title
        self.query_id = query_id
        self.up_count = 0
        self.down_count = 0
        self.likes = []
        self.dislikes = []

    def like_to_dislike(self, user):
        like = db.session.query(Like).filter_by(movie=self, user=user).first()
        db.session.delete(like)
        db.session.commit()
        if self.up_count <= 0:
            self.up_count = 0
        else:
            self.up_count -= 1

        dislike = Dislike(user=user, movie=self)
        self.down_count += 1
        db.session.add_all([dislike, self])
        db.session.commit()

    def dislike_to_like(self, user):
        dislike = db.session.query(Dislike).filter_by(
            movie=self, user=user).first()
        db.session.delete(dislike)
        db.session.commit()
        if self.down_count <= 0:
            self.down_count = 0
        else:
            self.down_count -= 1
        like = Like(user=user, movie=self)
        self.up_count += 1
        db.session.add_all([like, self])
        db.session.commit()

    def new_thumb_encounter(self, thumb, user):
        if thumb == 'up':
            like = Like(user=user, movie=self)
            self.up_count += 1
            db.session.add_all([like, self])
            db.session.commit()
        else:
            dislike = Dislike(user=user, movie=self)
            self.down_count += 1
            db.session.add_all([dislike, self])
            db.session.commit()

    def user_movie_check(self, user, thumb):
        if db.session.query(Like).filter_by(
                movie=self, user=user).first() is not None and thumb == 'down':
            self.like_to_dislike(user)
        elif db.session.query(Dislike).filter_by(
                movie=self, user=user).first() is not None and thumb == 'up':
            self.dislike_to_like(user)
        else:
            self.new_thumb_encounter(thumb, user)

    def create_and_like(self, thumb, user):
        if thumb == 'down':
            dislike = Dislike(movie=self, user=user)
            db.session.add(dislike)
            self.down_count += 1
        else:
            like = Like(movie=self, user=user)
            self.up_count += 1
            db.session.add(like)
        db.session.add(self)
        db.session.commit()


class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String)
    likes = db.relationship('Like', backref='user', lazy=True)
    dislikes = db.relationship('Dislike', backref='user', lazy=True)

    def __init__(self, uuid):
        self.uuid = uuid
        self.likes = []
        self.dislikes = []


class Like(db.Model):
    __tablename__ = 'like'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    movie_id = db.Column(db.Integer, db.ForeignKey("movie.id"), nullable=False)


class Dislike(db.Model):
    __tablename__ = 'dislike'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    movie_id = db.Column(db.Integer, db.ForeignKey("movie.id"), nullable=False)
# End of Models=================================


# schema creation
class MovieSchema(ma.Schema):
    class Meta:
        fields = ('id', 'title', 'query_id', 'up_count', 'down_count')


class LikeSchema(ma.Schema):
    movie = ma.Nested(MovieSchema)

    class Meta:
        fields = ('id', 'movie')


class DislikeSchema(ma.Schema):
    movie = ma.Nested(MovieSchema)

    class Meta:
        fields = ('id', 'movie')


class UserSchema(ma.Schema):
    likes = ma.Nested(LikeSchema, many=True)
    dislikes = ma.Nested(DislikeSchema, many=True)

    class Meta:
        fields = ('id', 'uuid', 'likes', 'dislikes')


# init Schemas
movie_schema = MovieSchema()
user_schema = UserSchema()
like_schema = LikeSchema()
dislike_schema = DislikeSchema()
movies_schema = MovieSchema(many=True)
likes_schema = LikeSchema(many=True)
dislikes_schema = DislikeSchema(many=True)


@app.route('/movies', methods=['POST'])
def create_movie():
    uuid = request.json["uuid"]
    query_id = request.json["query_id"]
    thumbs = request.json["thumbs"]
    title = request.json["title"]
    movie = db.session.query(Movie).filter_by(query_id=query_id).first()
    user = User.query.filter_by(uuid=uuid).first()
    # creating movie_user_check from past project.
    if movie is not None and user is not None:
        movie.user_movie_check(user, thumbs)
        output = movie_schema.dump(movie)
        return jsonify({"movie": output, "code": 200, "message": "successfully added movie and user to database"})
    elif movie is None and user is not None:
        movie = Movie(title, query_id)
        movie.create_and_like(thumbs, user)
        output = movie_schema.dump(movie)
        return jsonify({"movie": output, "code": 200, "message": "successfully added movie to database"})
    else:
        return jsonify({"message": "User not found", "code": 404, "status": "error"})


@app.route('/movies_check', methods=['POST'])
def get_movies():
    queries = request.json["queries"]
    result = []
    if(queries):
        for ele in queries:
            movie = Movie.query.filter_by(query_id=ele).first()
            if(movie is not None):
                found_movie = movie_schema.dump(movie)
                result.append(found_movie)
    return jsonify({"movies": result, "message": "all movies successfully received", "code": 200})


@app.route('/users', methods=['POST'])
def create_user():
    uuid = request.json["uuid"]
    new_user = User(uuid)
    db.session.add(new_user)
    db.session.commit()
    output = user_schema.dump(new_user)
    return jsonify({"user": output, "message": "user successfully created", "code": 200})


@app.route('/users/<uuid>', methods=['GET'])
def show_user_info(uuid):
    user = User.query.filter_by(uuid=uuid).first()
    if(user is None):
        return jsonify({'message': 'Sorry user is not saved', 'code': 400})
    output = user_schema.dump(user)
    return jsonify({"user": output, "message": "User info received successfully", "code": 200})


if __name__ == "__main__":
    app.run()
