from app import db, bcrypt
from datetime import datetime
from werkzeug.security import check_password_hash
from flask_login import UserMixin
from app import login
from datetime import datetime
from secrets import choice


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    email = db.Column(db.String(120), index=True, unique=True)
    password_hash = db.Column(db.String(128))
    win = db.Column(db.Integer, default=0)
    loss = db.Column(db.Integer, default=0)
    draw = db.Column(db.Integer, default=0)

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode("UTF-8")

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return '<User {}>'.format(self.username)


@login.user_loader
def load_user(id):
    return User.query.get(int(id))


class Deck:
    def __init__(self):
        self.deck = []
        symbols = ["S", "H", "C", "D"]
        numbers = [str(n) for n in range(2, 11)]
        royals = ["A", "K", "Q", "J"]
        faces = numbers + royals
        deck = [face + symbol for symbol in symbols for face in faces]
        # shuffle(deck)
        shuffled_deck = []
        while (len(shuffled_deck) < 20):
            card = choice(deck)
            shuffled_deck.append(card)
            deck.remove(card)
        self.deck = shuffled_deck


class Game(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    gamename = db.Column(db.String, nullable=False)
    no_players = db.Column(db.Integer)
    player1_name = db.Column(db.String, nullable=False, default="Not Joined Yet")
    player2_name = db.Column(db.String, nullable=False, default="Not Joined Yet")
    player1_id = db.Column(db.Integer)
    player2_id = db.Column(db.Integer)
    player1_score = db.Column(db.Integer, default=0)
    player2_score = db.Column(db.Integer, default=0)
    completed = db.Column(db.Integer, default=0)
    winner = db.Column(db.String)

    def __repr__(self):
        return '<Game %r>' % self.id


# GameMove is modeling the moves to keep track of game summaries post game completion
class GameMove(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, nullable=False)
    time = db.Column(db.DateTime, default=datetime.utcnow())
    turn_player_id = db.Column(db.Integer, nullable=False)
    turn_player_name = db.Column(db.String, nullable=False)
    player1_hand = db.Column(db.String)
    player2_hand = db.Column(db.String)
    player_action = db.Column(db.String, nullable=False)
    cards_played = db.Column(db.String)
    cards_bluffed = db.Column(db.String)

    def __repr__(self):
        return '<Move %r>' % self.id