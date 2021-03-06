from tutorlib.interface.alarm import Alarm
from tutorlib.interface.tutorial import Tutorial
from tutorlib.testing.tester import TutorialTester


def run_tests(tutorial, text):
    """
    Run the tests for the given tutorial.

    Testing and analysis will only be performed if no compilation errors were
    encountered when executing the student's code.

    This function uses an Alarm object to prevent infinite loops from causing
    MyPyTutor to hang.

    Args:
      tutorial (Tutorial): The tutorial to run the tests for.
      text (str): The student's code.

    Returns:
      A three-element tuple.

      The first element in the tuple will be the TutorialTester object which
      was run on the student's code.

      The second element in the tuple will be the CodeAnalyser object which was
      run on the student's code.

      The third element in the tuple will be the line number of any error found
      in the student's code, or None if no such error exists.

      Both the TutorialTester and the CodeAnalyser will be returned regardless
      of whether an error is encountered.  They will have as much state as was
      possible to determine before the error occurred.

    """
    # load the support file (giving students access to functions, variables
    # etc which they may need for their solution)
    _lcls = {}
    gbls, lcls = tutorial.exec_submodule(Tutorial.SUPPORT_MODULE, _lcls, None)

    # we rely on the implementation-specific behaviour of exec_submodule to
    # pass only a single dict to exec if lcls is given as None
    # if someone changes this behaviour, the submodule *will not* be parsed
    # correctly, so we should fail (see the note in exec_module)
    assert _lcls is gbls and _lcls is lcls

    # perform the static analysis
    # this should only take place if there are no errors in parsing the
    # student's code (as those would interfere with ast)
    # we therefore collect those first, and only proceed if there were
    # no such errors
    # note that we may have an error with no line information (this will be
    # the case with a NameError, for example)
    analyser = tutorial.analyser
    tester = TutorialTester(tutorial.test_classes, lcls)

    error_line = analyser.check_for_errors(text)
    if error_line is not None:
        return tester, analyser, error_line

    if not analyser.errors:
        # there were no errors, so it's safe to perform the analysis
        analyser.analyse(text)

    # set up our timeout alarm
    alarm = Alarm(tutorial.timeout)
    alarm.setDaemon(True)
    alarm.start()

    # we can always run the tests no matter what
    try:
        tester.run(text, tutorial.wrap_student_code)
    except KeyboardInterrupt:
        pass  # we're going to ignore this for now
    finally:
        alarm.stop_interrupt()

    return tester, analyser, None
