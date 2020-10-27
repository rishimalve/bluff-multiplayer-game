import uuid
import re
import logging
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_login import current_user, login_user
from flask_login import logout_user
from flask_login import login_required
from flask import Flask, render_template, redirect, flash, url_for, jsonify, request, Response
from config import Config
from flask_bcrypt import Bcrypt
from werkzeug.urls import url_parse
from flask_wtf.csrf import CSRFProtect
from flask import session
from datetime import timedelta

import time

logging.basicConfig(filename='logging.log', level=logging.CRITICAL,
                    format="%(asctime)s %(levelname)s %(name)s %(threadName)s : %(message)s")

app = Flask(__name__)


app.config.from_object(Config)
bcrypt = Bcrypt(app)
db = SQLAlchemy(app)
migrate = Migrate(app, db)
login = LoginManager(app)
login.login_view = 'login'
login.refresh_view = 'relogin'
login.needs_refresh_message = (u"Session timedout, please re-login")
login.needs_refresh_message_category = "info"

csrf = CSRFProtect(app)

from models import User, GameMove, Game, Deck
from forms import LoginForm
from forms import RegistrationForm


db.create_all()




@app.before_request
def before_request():
    session.permanent = True
    app.permanent_session_lifetime = timedelta(minutes=3)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user is None or not bcrypt.check_password_hash(user.password_hash, form.password.data):
            app.logger.info('%s failed to log in', form.username.data)
            flash('Invalid username or password')
            return redirect(url_for('login'))
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get('next')
        if not next_page or url_parse(next_page).netloc != '':
            next_page = url_for('index')
        session['user'] = form.username.data
        session['uid'] = uuid.uuid4()
        app.logger.info('%s logged in successfully', form.username.data)
        return redirect(next_page)
    return render_template('login.html', title='Sign In', form=form)


@app.route('/')
@login_required
def index():
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
    user = User.query.filter_by(username=current_user.username).first_or_404()
    users = User.query.all()
    return render_template('index.html', title='Home', user=user, users=users)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegistrationForm()
    regex_username = "^(?!.*[-_]{2,})(?=^[^-_].*[^-_]$)[\w\s-]{6,9}$"
    regex_pw = "^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,15}$"
    if form.validate_on_submit():
        if not bool(re.fullmatch(regex_username, form.username.data)):
            flash('Username must contain between 6-8 characters. '
                  'Must not start and end with any special character. '
                  'Must not contain special character other than - or _ in between.')
            return redirect(url_for('register'))
        if not bool(re.fullmatch(regex_pw, form.password.data)):
             flash('Password must contain between 8-15 characters. '
                   'Must contain at least one number and special character. '
                   'Must contain both lower and upper case characters.')
             return redirect(url_for('register'))
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Congratulations, you are now a registered user!')
        return redirect(url_for('index'))
    return render_template('register.html', title='Register', form=form)

@app.route("/how_to_play")
def how_to_play():
    return render_template("how_to_play.html")

@app.route("/games")
def show_games():
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
    games = [game for game in Game.query.all()]
    return render_template("games.html", games=games)


@app.route("/create_game", methods=['GET', 'POST'])
def create_game():
    gameName = request.form.get('gamename')
    user = User.query.filter_by(username=current_user.username).first_or_404()
    gamename_regex = "^[A-Za-z0-9]+$"
    if bool(Game.query.filter_by(gamename=gameName).first()) or not bool(re.fullmatch(gamename_regex, gameName)):
        return jsonify({"success": False})
    game = Game(gamename=gameName, no_players=1, player1_id=user.id, player1_name=user.username, winner="")
    db.session.add(game)
    db.session.commit()
    gm = GameMove(game_id=game.id, turn_player_id=game.player1_id, turn_player_name=game.player1_name, player_action="Start")
    db.session.add(gm)
    db.session.commit()
    return jsonify({"success": True})


def return_hand(game, user):
    gm = GameMove.query.filter_by(game_id=game.id).order_by(GameMove.id.desc()).first()
    if(gm.player1_hand is None):
        return "Hand not assigned yet"
    if game.player1_id == user.id:
        return gm.player1_hand
    else:
        return gm.player2_hand

    


@app.route("/join_game/<string:gameName>", methods=["GET","POST"])
def join_game(gameName):
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
    game = Game.query.filter_by(gamename=gameName).first()
    user = User.query.filter_by(username=current_user.username).first_or_404()
    if not bool(game):
        return "Sorry doesn't exist"
    if game.no_players == 1:
        if game.player1_id == user.id:
            pass
        else:
            game.player2_id = user.id
            game.player2_name = user.username
            game.no_players = 2
            deck = Deck().deck
            gm = GameMove(game_id=game.id, turn_player_id=game.player1_id, turn_player_name=game.player1_name,
            player1_hand=" ".join(deck[:10]),
            player2_hand=" ".join(deck[10:20]),
            player_action="seed hand")
            
            db.session.add(gm)
            db.session.commit()
    else:
        if not (game.player1_id == user.id or game.player2_id == user.id):
            return "filled to capacity"
    gm = GameMove.query.filter_by(game_id=game.id).order_by(GameMove.id.desc()).first()
    bluff_query = request.form.get('bluffquery', "  ")
    actual_query = request.form.get('actualquery', " ")
    actual_pattern = "^(((10|[0-9])|[AKQJ])[HCSD]\s)*(((10|[0-9])|[AKQJ])[HCSD])$"
    bluff_pattern = "^(10|[0-9])+ ((10|[0-9])|[AKQJ])$"
    game = Game.query.filter_by(gamename=gameName).first()
    gm = GameMove.query.filter_by(game_id=game.id).order_by(GameMove.id.desc()).first()
    actual_list = actual_query.split(" ")
    hand = return_hand(game, user)
    hand_list = hand.split(" ")
    if(get_turn(game) != user.id):
        return render_template("game_screen.html", user=user, hand=return_hand(game, user),
                               gamename=game.gamename, game=game)
    if not (set(actual_list)).issubset(set(hand_list)):
        return render_template("game_screen.html", user=user,
                                hand=return_hand(game, user), gamename=game.gamename, game=game)
    else:
        mod_hand = " ".join([h for h in hand_list if h not in actual_list])
    if gm.player1_hand == hand:
        new_gm = GameMove(game_id=game.id, turn_player_id=user.id, turn_player_name=user.username,
                            player1_hand=mod_hand,
                            player2_hand=gm.player2_hand, player_action="play cards",
                            cards_played=actual_query,
                            cards_bluffed=bluff_query)
    else:
        new_gm = GameMove(game_id=game.id, turn_player_id=user.id, turn_player_name=user.username,
                            player1_hand=gm.player1_hand,
                            player2_hand=mod_hand, player_action="play cards",
                            cards_played=actual_query,
                            cards_bluffed=bluff_query)
    db.session.add(new_gm)
    db.session.commit()
    return render_template("game_screen.html", user=user, hand=return_hand(game, user),
                               gamename=game.gamename, game=game)

def get_turn(game):
    gm = GameMove.query.filter_by(game_id=game.id).order_by(GameMove.id.desc()).first()
    if not gm:
        return -1
    if gm.turn_player_id == game.player1_id:
        return game.player2_id
    else:
        return game.player1_id

def move_populate(game, user):
    time.sleep(0.01)
    gm = GameMove.query.filter_by(game_id=game.id).order_by(GameMove.id.desc()).first()
    if "Start" == gm.player_action:
        return "Waiting for players" + ";" + "N/A" + ";" + "N/A" + ";" +str(game.winner) + ";" + str(return_hand(game, user)) + ";" + str(get_turn(game) == user.id)
    else:
        if(gm.player_action=="seed hand"):
            return "Waiting for first move" + ";" + str(game.player1_score) +";" + str(game.player2_score) + ";" + str(game.winner) + ";" + str(return_hand(game, user)) + ";" + str(get_turn(game) == user.id)
        else:
            return str(gm.cards_bluffed) +";"  + str(game.player1_score) +";" + str(game.player2_score) + ";" + str(game.winner) + ";" + str(return_hand(game, user)) + ";" + str(get_turn(game) == user.id)
        

@app.route('/stream/<string:params>',methods=["GET","POST"])
def stream(params):
    gameName, username = params.split("&")
    user = User.query.filter_by(username= username).first_or_404()
    game=Game.query.filter_by(gamename=gameName).first()
    def event_stream(game, user):
        while True:
            yield 'data: {}\n\n'.format(move_populate(game, user))
    return Response(event_stream(game, user), mimetype="text/event-stream")


@app.route("/call_bluff/<string:gameName>")
def call_bluff(gameName):
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
    user = User.query.filter_by(username=current_user.username).first_or_404()
    game = Game.query.filter_by(gamename=gameName).first()
    gm = GameMove.query.filter_by(game_id=game.id).order_by(GameMove.id.desc()).first()
    if (not get_turn(game) == user.id):
       return redirect(
            url_for("join_game", user=user, game=game,
                    hand=return_hand(game, user),
                    gameName=game.gamename))
    if (gm.cards_bluffed == "Bluff Called" or gm.player_action=="pass"):
        return redirect(
            url_for("join_game", user=user, game=game,
                    hand=return_hand(game, user),
                    gameName=game.gamename))
    bluff = gm.cards_bluffed
    actual = gm.cards_played
    a_cards = actual.split(" ")
    b_cards = bluff.split(" ")
    count = b_cards[0]
    flag = 0
    for i in a_cards:
        card = i[:-1]
        if b_cards[1] == card:
            flag += 1
    if str(flag) == count:
        flash("Cards were real. Better luck next time!")
        if user.id == game.player1_id:
            game.player1_score -= 2
            game.player2_score += 2
        else:
            game.player2_score -= 2
            game.player1_score += 2
    else:
        flash("You've caught a bluff!")
    name = ""
    if game.player2_score >= 10:
        name = User.query.filter_by(id=game.player2_id).first_or_404().username
    if game.player1_score >= 10:
        name = User.query.filter_by(id=game.player2_id).first_or_404().username
    if(bool(name)):
        winner = User.query.filter_by(id=game.player2_id).first_or_404()
        winner.win += 1
        loser = User.query.filter_by(id=game.player1_id).first_or_404()
        loser.loss += 1
        game.completed = 1
        game.winner = name
    new_gm = GameMove(game_id=game.id, turn_player_id=user.id, turn_player_name=user.username,
                      player1_hand=gm.player1_hand,
                      player2_hand=gm.player2_hand, player_action="call a bluff",
                      cards_played=" ",
                      cards_bluffed="Bluff Called")
    db.session.add(new_gm)
    db.session.commit()
    return redirect(url_for("join_game",gameName=game.gamename))


@app.route("/completed_games")
def completed_games():
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
    games = Game.query.filter_by(completed=1).all()
    return render_template('completed_games.html', title='Completed Games', games=games)


@app.route("/show_moves/<string:gamename>")
def show_moves(gamename):
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
    game = Game.query.filter_by(gamename=gamename).first()
    gameMoves = GameMove.query.all()
    return render_template('moves.html', title='Moves', game=game, gameMoves=gameMoves)


@app.route("/pass_move/<string:gamename>")
def pass_move(gamename):
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
    user = User.query.filter_by(username=current_user.username).first_or_404()
    game = Game.query.filter_by(gamename=gamename).first()
    gm = GameMove.query.filter_by(game_id=game.id).order_by(GameMove.id.desc()).first()
    if (get_turn(game) == user.id):
        bluff = GameMove.query.filter_by(game_id=game.id).order_by(GameMove.id.desc()).first().cards_bluffed
        actual = GameMove.query.filter_by(game_id=game.id).order_by(GameMove.id.desc()).first().cards_played
        new_gm = GameMove(game_id=game.id, turn_player_id=user.id, turn_player_name=user.username,
                          player1_hand=gm.player1_hand,
                          player2_hand=gm.player2_hand, player_action="pass",
                          cards_played=actual,
                          cards_bluffed="Passed")
        db.session.add(new_gm)
        db.session.commit()
    return redirect(url_for("join_game",gameName=game.gamename))
       

if __name__ == '__main__':
    app.run(ssl_context=('cert.pem', 'key.pem'))








