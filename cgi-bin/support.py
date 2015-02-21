"""
At the moment, we're storing all our data on the filesystem, presumably so that
we don't have to bother with a database.

In order to make any later transition easier, the filesystem-specific code (ie,
all the code which access files or is otherwise aware that we're using the
filesystem like this) has been extracted into this file.

The cgi code should remain unaware of the underlying storage mechanisms.

File structure:
  base_dir/
    mpt_version                      <- MyPyTutor version file
    data/
      answers/
        <username>/
          <tutorial_package_name>/
            <problem_set_name>/
              <tutorial_name>        <- answer file, with python code
      submissions/
        tutorial_hashes              <- tutorial hashes / info file
        <username>/
          submission_log             <- student submission log
          admin_log                  <- log of admin actions taken on the user
          <tutorial_problem_hash>    <- the student's answer, as submitted

"""
import base64
from collections import namedtuple
from datetime import datetime
import dateutil.parser
import hashlib
import json
import os
from werkzeug.utils import secure_filename
from zipfile import ZipFile


# base directory for server file storage
BASE_DIR = "/opt/local/share/MyPyTutor/MPT3_CSSE1001"

# where student data is to be put/found
PUBLIC_DIR = os.path.join(BASE_DIR, "public")
DATA_DIR = os.path.join(BASE_DIR, "data")
ANSWERS_DIR = os.path.join(DATA_DIR, "answers")
SUBMISSIONS_DIR = os.path.join(DATA_DIR, "submissions")
USER_INFO_FILE = os.path.join(DATA_DIR, "user_info")

# submission specific constants
TUTORIAL_HASHES_FILE = os.path.join(SUBMISSIONS_DIR, "tutorial_hashes")
TUTORIAL_HASH_MAPPINGS_FILE = os.path.join(
    SUBMISSIONS_DIR, "tutorial_hash_mappings",
)
SUBMISSION_LOG_NAME = "submission_log"
ADMIN_LOG_NAME = "admin_log"
DUE_DATE_FORMAT = "%H_%d/%m/%y"

# MyPyTutor version file
MPT_VERSION_FILE = os.path.join(BASE_DIR, 'mpt_version')

# Tutorial zipfile
TUTORIALS_ZIP_PATH = os.path.join(PUBLIC_DIR, 'CSSE1001Tutorials.zip')


def _get_answer_path(user, tutorial_package_name, problem_set_name,
        tutorial_name, create_dir=False):
    """
    Get a path indicating where the server copy of the student's answer to the
    given tutorial problem should be stored.

    Note that it's possible for students to rename the tutorial package (and
    theoretically also the problem sets, but with a lot more work).  This
    function will make use of whatever name the student has chosen to assign
    to the tutorial package.
    Because we just store copies of the answer, and don't do any checking off
    this directly, that's not an issue.  (After all, we're just looking to
    mirror, in a sense, the local filesystem.)

    The only way we could end up with issues is if the student creates two
    installations of MyPyTutor, with different names for the same package, and
    then syncs both of them with the server.

    Args:
      user (str): The username of the current user.
      tutorial_package_name (str): The name of the tutorial package (eg, for
          UQ students, this will be something like 'CSSE1001Tutorials').
      problem_set_name (str): The name of the problem set (eg, 'Introduction').
      tutorial_name (str): The name of the tutorial problem (note that this
          will be, eg, 'Using Functions', not 'fun1.tut').
      create_dir (bool, optional): Whether to create the problem set directory
          if it does not already exist.  Defaults to False.

    Returns:
      The path to the answer file for the given tutorial details.
      None if the problem_set does not exist, and create_dir is False.

    """
    # sanitise the path components
    # this is essential to avoid, eg, tutorial_name='hi/../../passwords.uhoh'
    tutorial_package_name = secure_filename(tutorial_package_name)
    problem_set_name = secure_filename(problem_set_name)
    tutorial_name = secure_filename(tutorial_name)

    # create/get our directory structure
    problem_set_dir = os.path.join(
        ANSWERS_DIR,
        user,
        tutorial_package_name,
        problem_set_name,
    )
    if not os.path.exists(problem_set_dir):
        if not create_dir:
            return None

        os.makedirs(problem_set_dir)  # TODO: set mode

    return os.path.join(problem_set_dir, tutorial_name)


def read_answer(user, tutorial_package_name, problem_set_name, tutorial_name):
    """
    Read the relevant answer for the given user.

    Args:
      user (str): The username of the current user.
      tutorial_package_name (str): The name of the tutorial package (eg, for
          UQ students, this will be something like 'CSSE1001Tutorials').
      problem_set_name (str): The name of the problem set (eg, 'Introduction').
      tutorial_name (str): The name of the tutorial problem (note that this
          will be, eg, 'Using Functions', not 'fun1.tut').

    Returns:
      None if there exists no such answer on the server.
      The text contents of the answer file otherwise.

    """
    path = _get_answer_path(
        user, tutorial_package_name, problem_set_name, tutorial_name,
        create_dir=True,
    )
    if path is None or not os.path.exists(path):
        return None

    with open(path) as f:
        return f.read()


def write_answer(user, tutorial_package_name, problem_set_name, tutorial_name,
        code):
    """
    Write the relevant answer for the given user using the given code.

    Args:
      user (str): The username of the current user.
      tutorial_package_name (str): The name of the tutorial package (eg, for
          UQ students, this will be something like 'CSSE1001Tutorials').
      problem_set_name (str): The name of the problem set (eg, 'Introduction').
      tutorial_name (str): The name of the tutorial problem (note that this
          will be, eg, 'Using Functions', not 'fun1.tut').
      code (str): The code to write to the answer file.

    """
    path = _get_answer_path(
        user, tutorial_package_name, problem_set_name, tutorial_name,
        create_dir=True,
    )

    with open(path, 'w') as f:
        f.write(code)


def get_answer_hash(user, tutorial_package_name, problem_set_name,
        tutorial_name):
    """
    Get the hash of the student's current answer to the relevant question.

    Args:
      user (str): The username of the current user.
      tutorial_package_name (str): The name of the tutorial package (eg, for
          UQ students, this will be something like 'CSSE1001Tutorials').
      problem_set_name (str): The name of the problem set (eg, 'Introduction').
      tutorial_name (str): The name of the tutorial problem (note that this
          will be, eg, 'Using Functions', not 'fun1.tut').

    Returns:
      None if the answer does not exist on the server.
      A base32 encoding of the sha512 hash of the server copy of the student's
      answer to the relevant question, otherwise.

    """
    code = read_answer(
        user, tutorial_package_name, problem_set_name, tutorial_name
    )
    if code is None:
        return None

    data = code.encode('utf8')
    answer_hash = hashlib.sha512(data).digest()

    b32_bytes = base64.b32encode(answer_hash)
    b32_str = b32_bytes.decode('ascii')

    return b32_str


def get_answer_modification_time(user, tutorial_package_name, problem_set_name,
        tutorial_name):
    """
    Get the last modification time of the student's current answer to the
    relevant question.

    Args:
      user (str): The username of the current user.
      tutorial_package_name (str): The name of the tutorial package (eg, for
          UQ students, this will be something like 'CSSE1001Tutorials').
      problem_set_name (str): The name of the problem set (eg, 'Introduction').
      tutorial_name (str): The name of the tutorial problem (note that this
          will be, eg, 'Using Functions', not 'fun1.tut').

    Returns:
      None if the answer does not exist on the server.
      The last-modified time of the answer, as a unix timestamp, otherwise.

    """
    path = _get_answer_path(
        user, tutorial_package_name, problem_set_name, tutorial_name,
        create_dir=True,
    )
    if path is None or not os.path.exists(path):
        return None

    return os.path.getmtime(path)


TutorialInfo = namedtuple(
    'TutorialInfo',
    ['hash', 'due', 'package_name', 'problem_set_name', 'tutorial_name']
)


# TODO: refactor the two functions below maybe?
# (look at how each of them is used and maybe there'll be a smarter way)
def get_tutorials():
    """
    Get a list of all tutorials, as TutorialInfo objects.

    Returns:
      An ordered list of TutorialInfo objects.
    """
    tutorials = []
    with open(TUTORIAL_HASHES_FILE) as f:
        for line in filter(None, map(str.strip, f)):
            hash_str, due_date_str, pkg_name, pset_name, tut_name \
                = line.split()

            due_date = datetime.strptime(due_date_str, DUE_DATE_FORMAT)

            tutorial_info = TutorialInfo(
                hash_str, due_date, pkg_name, pset_name, tut_name
            )
            tutorials.append(tutorial_info)
    return tutorials


def parse_tutorial_hashes():
    """
    Get all valid tutorial hashes, as TutorialInfo objects.

    Format of tutorial_hashes file:
      hash due_hh_dd_mm_yy package_name problem_set_name tutorial_name

    It is assumed that there will be no hash collisions.  If there are, this
    can be fixed by editing one of the package files ;)

    Hashes are sha512, encoded as base32 strings.

    This function assumes that the tutorial_hashes file is in the correct
    format, and so does not handle errors which would result from a
    badly-formatted file.

    Returns:
      A dictionary mapping hashes to the corresponding TutorialInfo objects.

      This makes use both of information both in the tututorial hashes file,
      and of the tutorial hash mappings which reflect changes to tutorials.

      Multiple hashes may therefore map to the same TutorialInfo object.

    """
    hashes = {}

    # get the current tutorial set
    with open(TUTORIAL_HASHES_FILE) as f:
        for line in filter(None, map(str.strip, f)):
            hash_str, due_date_str, pkg_name, pset_name, tut_name \
                = line.split()

            due_date = datetime.strptime(due_date_str, DUE_DATE_FORMAT)

            tutorial_info = TutorialInfo(
                hash_str, due_date, pkg_name, pset_name, tut_name
            )
            hashes[tutorial_info.hash] = tutorial_info

    # get the changes
    with open(TUTORIAL_HASH_MAPPINGS_FILE) as f:
        hash_mappings = json.loads(f.read())

    # resolve all mappings to the current TutorialInfo object (but only if
    # that is possible -- ignore removed tutorials)
    def resolve_hash(tutorial_hash):
        if tutorial_hash in hashes:
            return hashes[tutorial_hash]
        if tutorial_hash in hash_mappings:
            return resolve_hash(hash_mappings[tutorial_hash])
        return None

    resolved_hashes = {h: resolve_hash(h) for h in hash_mappings}
    resolved_hashes = {
        h: ti for h, ti in resolved_hashes.items() if ti is not None
    }

    # update our existing hashes
    # don't check for hash collisions - that would be a server error
    # checking for collisions is the responsibility of the hash file
    # generation scripts
    hashes.update(resolved_hashes)

    return hashes


def _get_or_create_user_submissions_dir(user):
    """
    Get the submissions directory for the user.

    If the directory does not exist, create it.

    Assumes that the username cannot be spoofed (and so does not need to be
    sanitised prior to use).

    Args:
      user (str): The username to get the submissions directory for.

    Returns:
      The path to the submissions directory for the given user.

    """
    submissions_path = os.path.join(SUBMISSIONS_DIR, user)

    if not os.path.exists(submissions_path):
        os.mkdir(submissions_path)  # TODO: mode

    return submissions_path


def _get_or_create_user_submissions_file(user):
    """
    Get the path to the submissions log file for the given user.

    The file will be created if it does not exist.

    Args:
      user (str): The username to get the submissions file for.

    Returns:
      The path to the submissions file for the given user.

    """
    # we assume that the username does not need sanitisation
    user_submissions_dir = _get_or_create_user_submissions_dir(user)
    submission_log_path = os.path.join(
        user_submissions_dir, SUBMISSION_LOG_NAME
    )

    # create the file if it does not exist
    if not os.path.exists(submission_log_path):
        with open(submission_log_path, 'w') as f:
            pass

    return submission_log_path


def _get_or_create_admin_log_file(user):
    user_submissions_dir = _get_or_create_user_submissions_dir(user)
    admin_log_path = os.path.join(
        user_submissions_dir, ADMIN_LOG_NAME
    )

    # create the file if it does not exist
    if not os.path.exists(admin_log_path):
        with open(admin_log_path, 'w') as f:
            pass

    return admin_log_path


TutorialSubmission = namedtuple('TutorialSubmission',
                                ['hash', 'date', 'allow_late'])


def parse_submission_log(user):
    """
    Get the submission log for the given user.

    Format of submission_log file:
      hash submitted_dd_mm_yy

    Format of the admin_log file:
      action_type [data ...]
    Valid action types:
      - 'allow_late', with data being the hash of the problem the student is
        allowed to submit late without penalty.

    Hashes are sha512, encoded as base32 strings.

    We don't store information in the submission_log about whether or not the
    tutorial was submittted on time, as that would be redundant.

    Args:
      user (str): The username to get the submissions log for.

    Returns:
      A list of TutorialSubmission objects representing the user's submissions.

    """
    data = []

    submission_log_path = _get_or_create_user_submissions_file(user)
    admin_log_path = _get_or_create_admin_log_file(user)

    with open(admin_log_path) as f:
        allow_lates = [line[1]
                       for line in filter(None, map(str.split, f))
                       if line[0] == 'allow_late']

    # parse the submission log file
    with open(submission_log_path) as f:
        for line in filter(None, map(str.strip, f)):
            hash_str, submitted_date_str = line.split()

            submitted_date = dateutil.parser.parse(submitted_date_str)
            allow_late = hash_str in allow_lates

            submission_info = TutorialSubmission(hash_str,
                                                 submitted_date,
                                                 allow_late)
            data.append(submission_info)

    return data


def add_submission(user, tutorial_hash, code):
    """
    Submit the tutorial with the given hash for the given user.

    This involves updating the user's submission log, as well as saving the
    actual code to disk.

    Args:
      user (str): The user who submitted the tutorial problem answer.
      tutorial_hash (str): The tutorial hash, as a base32 string.
      code (str): The user's code.

    Returns:
      A TutorialSubmission object corresponding to the submission.
      None if the submission could not be added.

    """
    # build our data
    # TODO: check for possible timezone issues (if submissions are made within 10 hours of the deadline)
    submitted_date = datetime.now()
    submitted_date_str = submitted_date.isoformat()

    submission = TutorialSubmission(tutorial_hash, submitted_date, False)

    # write to the log
    submission_log_path = _get_or_create_user_submissions_file(user)

    with open(submission_log_path, 'a') as f:
        f.write(' '.join([tutorial_hash, submitted_date_str]) + '\n')

    # a base32 hash should NEVER need to be sanitised, with the exception of
    # removing the padding characters
    # if it does, something is VERY wrong
    stripped_b32_hash = tutorial_hash.strip('=')
    if stripped_b32_hash != secure_filename(stripped_b32_hash):
        return None

    # write the student's code to file
    # this file should not exist, but if it does, overwrite it
    user_submissions_dir = _get_or_create_user_submissions_dir(user)
    answer_path = os.path.join(user_submissions_dir, stripped_b32_hash)

    with open(answer_path, 'w') as f:
        f.write(code)

    # return the TutorialSubmission object
    return submission

def get_submissions_for_user(user):
    """
    Return the submissions for the given user.

    No attempt is made to check that the logged in user has permission to view
    these submissions.  That is the responsibility of the caller.

    Args:
      user (str): The user to return the submissions for.

    Returns:
      A list of two-element tuples.
      Each tuple represents a single tutorial.

      The first element in the tuple is the hash of the tutorial package (in
      the same format as usual, ie base32 encoded sha512 hash).

      The second element in the tuple is one of the strings
      {'MISSING', 'OK', 'LATE', 'LATE_OK'}.

    """
    # get our data
    hashes = parse_tutorial_hashes()
    submissions = parse_submission_log(user)
    tutorials = set(hashes.values())

    # check if our submissions are late or not
    results = {ti.hash: 'MISSING' for ti in tutorials}

    for submission in submissions:
        # lookup, not get, as this must exist: if not, then we have a
        # submission with an unknown tutorial, which is a server error
        tutorial_info = hashes[submission.hash]

        if submission.date <= tutorial_info.due:
            status = 'OK'
        elif submission.allow_late:
            status = 'LATE_OK'
        else:
            status = 'LATE'

        results[tutorial_info.hash] = status

    return results


def set_allow_late(user, tutorial_hash):
    """
    Allow a user to submit a tutorial late without incurring a mark penalty.
    If the user has not yet submitted, they will be allowed to submit late.

    This function assumes that the invoker has sufficient privilege to take
    this action.

    Args:
      user (str): The username to set the late allowance on.
      tutorial_hash (str): The tutorial hash, as a base32 string.
    """
    admin_log_path = _get_or_create_admin_log_file(user)

    with open(admin_log_path, 'a') as f:
        f.write('allow_late {}\n'.format(tutorial_hash))


def has_allow_late(user, tutorial_hash):
    """
    Return True if the user has the 'allow_late' flag set on the given
    tutorial.
    """
    admin_log_path = _get_or_create_admin_log_file(user)

    with open(admin_log_path, 'a') as f:
        return any(line[0] == 'allow_late' and line[1] == tutorial_hash
                   for line in map(str.split, f))


User = namedtuple('User', ['id', 'name', 'email', 'enrolled'])

ENROLLED = 'enrolled'
NOT_ENROLLED = 'not_enrolled'

def get_users(query='', enrol_filter=None, sort_key=None):
    """Return a list of users, optionally filtered/sorted.

    Args:
      query (str, optional): A string to filter results on. If given, return
          only those users whose id/name/email contains the given string.
      enrol_filter (str, optional): One of ENROLLED/NOT_ENROLLED. If given,
          return only those users whose enrolment status matches the parameter.
      sort_key (function, optional): A key-function to sort the users on.
          Defaults to sorting on user's id.

    Returns:
        A list of User objects, filtered/sorted accordingly.
    """
    with open(USER_INFO_FILE, 'rU') as f:
        users = []
        for line in f:
            if line.startswith('#'):
                continue
            id, name, email, enrolled = line.strip().split(',')
            # check if the query string is contained in id or name or email and
            # the enrol_filter matches the given enrol state, if given.
            if (any(query.lower() in x.lower() for x in (id, name, email))
                    and (enrol_filter is None or enrol_filter == enrolled)):
                users.append(User(id, name, email, enrolled))
    if sort_key is None:
        sort_key = lambda u: u.id
    users.sort(key=sort_key)
    return users


def get_user(userid):
    """Return known metadata about a single user (or None, if unknown)."""
    with open(USER_INFO_FILE, 'rU') as f:
        for line in f:
            if line.startswith('#'):
                continue
            info = line.strip().split(',')
            if userid == info[0]:
                return User(*info)
    return None


def add_user(user):
    """Adds a user to the user_info file, if they don't already exist.
    This function should get called whenever a new user interacts with the
    system, or when an administrator imports a list of users.

    If the user's ID already exists in the records, no action is taken (even if
    the rest of the information is different).

    Args:
      user (support.User): The user to add information about.

    Returns:
      True if the user was added, False if the user already existed.
    """
    # TODO: This implementation might cause a race condition if the user is
    # added by another process while this process is reading the file.
    # TODO: This is also possibly too slow (imagine ~600 users, this function
    # probably gets called any time any of them attempts an action)
    with open(USER_INFO_FILE, 'rU') as f:
        for line in f:
            if line.startswith('#'):
                continue
            info = line.strip().split(',')
            if user.id == info[0]:
                return False

    with open(USER_INFO_FILE, 'a') as f:
        f.write('{0.id},{0.name},{0.email},{0.enrolled}\n'.format(user))
        return True


def get_mypytutor_version():
    """
    Return the current MyPyTutor version.

    The MyPyTutor version file must exist on the filesystem.

    Returns:
      The MyPyTutor version, as a string.

    """
    with open(MPT_VERSION_FILE) as f:
        return f.read().strip()


def get_tutorials_timestamp():
    """
    Return the timestamp of the current tutorial package for CSSE1001.

    The package must exist.

    Returns:
      The tutorial package creation time, as a Unix time string.

    """
    with ZipFile(TUTORIALS_ZIP_PATH) as zf:
        with zf.open('config.txt') as f:
            return f.readline().strip()  # we just need the first line

