# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import atexit
import json
import os
import pathlib
import sys
import traceback


import pytest

script_dir = pathlib.Path(__file__).parent.parent
sys.path.append(os.fspath(script_dir))
sys.path.append(os.fspath(script_dir / "lib" / "python"))

from testing_tools import socket_manager  # noqa: E402
from typing import Any, Dict, List, Optional, Union, TypedDict, Literal  # noqa: E402


class TestData(TypedDict):
    """A general class that all test objects inherit from."""

    name: str
    path: pathlib.Path
    type_: Literal["class", "function", "file", "folder", "test", "error"]
    id_: str


class TestItem(TestData):
    """A class defining test items."""

    lineno: str
    runID: str


class TestNode(TestData):
    """A general class that handles all test data which contains children."""

    children: "list[Union[TestNode, TestItem, None]]"


class VSCodePytestError(Exception):
    """A custom exception class for pytest errors."""

    def __init__(self, message):
        super().__init__(message)


ERRORS = []
IS_DISCOVERY = False
map_id_to_path = dict()
collected_tests_so_far = list()
TEST_RUN_PIPE = os.getenv("TEST_RUN_PIPE")
SYMLINK_PATH = None


def pytest_load_initial_conftests(early_config, parser, args):
    global TEST_RUN_PIPE
    TEST_RUN_PIPE = os.getenv("TEST_RUN_PIPE")
    error_string = (
        "PYTEST ERROR: TEST_RUN_PIPE is not set at the time of pytest starting. "
        "Please confirm this environment variable is not being changed or removed "
        "as it is required for successful test discovery and execution."
        f"TEST_RUN_PIPE = {TEST_RUN_PIPE}\n"
    )
    if not TEST_RUN_PIPE:
        print(error_string, file=sys.stderr)
    if "--collect-only" in args:
        global IS_DISCOVERY
        IS_DISCOVERY = True

    # check if --rootdir is in the args
    for arg in args:
        if "--rootdir=" in arg:
            rootdir = arg.split("--rootdir=")[1]
            if not os.path.exists(rootdir):
                raise VSCodePytestError(
                    f"The path set in the argument --rootdir={rootdir} does not exist."
                )

            # Check if the rootdir is a symlink or a child of a symlink to the current cwd.
            isSymlink = False

            if os.path.islink(rootdir):
                isSymlink = True
                print(
                    f"Plugin info[vscode-pytest]: rootdir argument, {rootdir}, is identified as a symlink."
                )
            elif pathlib.Path(os.path.realpath(rootdir)) != rootdir:
                print("Plugin info[vscode-pytest]: Checking if rootdir is a child of a symlink.")
                isSymlink = has_symlink_parent(rootdir)
            if isSymlink:
                print(
                    f"Plugin info[vscode-pytest]: rootdir argument, {rootdir}, is identified as a symlink or child of a symlink, adjusting pytest paths accordingly.",
                )
                global SYMLINK_PATH
                SYMLINK_PATH = pathlib.Path(rootdir)


def pytest_internalerror(excrepr, excinfo):
    """A pytest hook that is called when an internal error occurs.

    Keyword arguments:
    excrepr -- the exception representation.
    excinfo -- the exception information of type ExceptionInfo.
    """
    # call.excinfo.exconly() returns the exception as a string.
    ERRORS.append(excinfo.exconly() + "\n Check Python Test Logs for more details.")


def pytest_exception_interact(node, call, report):
    """A pytest hook that is called when an exception is raised which could be handled.

    Keyword arguments:
    node -- the node that raised the exception.
    call -- the call object.
    report -- the report object of either type CollectReport or TestReport.
    """
    # call.excinfo is the captured exception of the call, if it raised as type ExceptionInfo.
    # call.excinfo.exconly() returns the exception as a string.
    # If it is during discovery, then add the error to error logs.
    if IS_DISCOVERY:
        if call.excinfo and call.excinfo.typename != "AssertionError":
            if report.outcome == "skipped" and "SkipTest" in str(call):
                return
            ERRORS.append(call.excinfo.exconly() + "\n Check Python Test Logs for more details.")
        else:
            ERRORS.append(report.longreprtext + "\n Check Python Test Logs for more details.")
    else:
        # If during execution, send this data that the given node failed.
        report_value = "error"
        if call.excinfo.typename == "AssertionError":
            report_value = "failure"
        node_id = get_absolute_test_id(node.nodeid, get_node_path(node))
        if node_id not in collected_tests_so_far:
            collected_tests_so_far.append(node_id)
            item_result = create_test_outcome(
                node_id,
                report_value,
                "Test failed with exception",
                report.longreprtext,
            )
            collected_test = testRunResultDict()
            collected_test[node_id] = item_result
            cwd = pathlib.Path.cwd()
            execution_post(
                os.fsdecode(cwd),
                "success",
                collected_test if collected_test else None,
            )


def has_symlink_parent(current_path):
    """Recursively checks if any parent directories of the given path are symbolic links."""
    # Convert the current path to an absolute Path object
    curr_path = pathlib.Path(current_path)
    print("Checking for symlink parent starting at current path: ", curr_path)

    # Iterate over all parent directories
    for parent in curr_path.parents:
        # Check if the parent directory is a symlink
        if os.path.islink(parent):
            print(f"Symlink found at: {parent}")
            return True
    return False


def get_absolute_test_id(test_id: str, testPath: pathlib.Path) -> str:
    """A function that returns the absolute test id. This is necessary because testIds are relative to the rootdir.
    This does not work for our case since testIds when referenced during run time are relative to the instantiation
    location. Absolute paths for testIds are necessary for the test tree ensures configurations that change the rootdir
    of pytest are handled correctly.

    Keyword arguments:
    test_id -- the pytest id of the test which is relative to the rootdir.
    testPath -- the path to the file the test is located in, as a pathlib.Path object.
    """
    split_id = test_id.split("::")[1:]
    absolute_test_id = "::".join([str(testPath), *split_id])
    return absolute_test_id


def pytest_keyboard_interrupt(excinfo):
    """A pytest hook that is called when a keyboard interrupt is raised.

    Keyword arguments:
    excinfo -- the exception information of type ExceptionInfo.
    """
    # The function execonly() returns the exception as a string.
    ERRORS.append(excinfo.exconly() + "\n Check Python Test Logs for more details.")


class TestOutcome(Dict):
    """A class that handles outcome for a single test.

    for pytest the outcome for a test is only 'passed', 'skipped' or 'failed'
    """

    test: str
    outcome: Literal["success", "failure", "skipped", "error"]
    message: Union[str, None]
    traceback: Union[str, None]
    subtest: Optional[str]


def create_test_outcome(
    testid: str,
    outcome: str,
    message: Union[str, None],
    traceback: Union[str, None],
    subtype: Optional[str] = None,
) -> TestOutcome:
    """A function that creates a TestOutcome object."""
    return TestOutcome(
        test=testid,
        outcome=outcome,
        message=message,
        traceback=traceback,  # TODO: traceback
        subtest=None,
    )


class testRunResultDict(Dict[str, Dict[str, TestOutcome]]):
    """A class that stores all test run results."""

    outcome: str
    tests: Dict[str, TestOutcome]


@pytest.hookimpl(hookwrapper=True, trylast=True)
def pytest_report_teststatus(report, config):
    """
    A pytest hook that is called when a test is called. It is called 3 times per test,
      during setup, call, and teardown.
    Keyword arguments:
    report -- the report on the test setup, call, and teardown.
    config -- configuration object.
    """
    cwd = pathlib.Path.cwd()
    if SYMLINK_PATH:
        cwd = SYMLINK_PATH

    if report.when == "call":
        traceback = None
        message = None
        report_value = "skipped"
        if report.passed:
            report_value = "success"
        elif report.failed:
            report_value = "failure"
            message = report.longreprtext
        try:
            node_path = map_id_to_path[report.nodeid]
        except KeyError:
            node_path = cwd
        # Calculate the absolute test id and use this as the ID moving forward.
        absolute_node_id = get_absolute_test_id(report.nodeid, node_path)
        if absolute_node_id not in collected_tests_so_far:
            collected_tests_so_far.append(absolute_node_id)
            item_result = create_test_outcome(
                absolute_node_id,
                report_value,
                message,
                traceback,
            )
            collected_test = testRunResultDict()
            collected_test[absolute_node_id] = item_result
            execution_post(
                os.fsdecode(cwd),
                "success",
                collected_test if collected_test else None,
            )
    yield


ERROR_MESSAGE_CONST = {
    2: "Pytest was unable to start or run any tests due to issues with test discovery or test collection.",
    3: "Pytest was interrupted by the user, for example by pressing Ctrl+C during test execution.",
    4: "Pytest encountered an internal error or exception during test execution.",
    5: "Pytest was unable to find any tests to run.",
}


@pytest.hookimpl(hookwrapper=True, trylast=True)
def pytest_runtest_protocol(item, nextitem):
    map_id_to_path[item.nodeid] = get_node_path(item)
    skipped = check_skipped_wrapper(item)
    if skipped:
        absolute_node_id = get_absolute_test_id(item.nodeid, get_node_path(item))
        report_value = "skipped"
        cwd = pathlib.Path.cwd()
        if absolute_node_id not in collected_tests_so_far:
            collected_tests_so_far.append(absolute_node_id)
            item_result = create_test_outcome(
                absolute_node_id,
                report_value,
                None,
                None,
            )
            collected_test = testRunResultDict()
            collected_test[absolute_node_id] = item_result
            execution_post(
                os.fsdecode(cwd),
                "success",
                collected_test if collected_test else None,
            )
    yield


def check_skipped_wrapper(item):
    """A function that checks if a test is skipped or not by check its markers and its parent markers.

    Returns True if the test is marked as skipped at any level, False otherwise.

    Keyword arguments:
    item -- the pytest item object.
    """
    if item.own_markers:
        if check_skipped_condition(item):
            return True
    parent = item.parent
    while isinstance(parent, pytest.Class):
        if parent.own_markers:
            if check_skipped_condition(parent):
                return True
        parent = parent.parent
    return False


def check_skipped_condition(item):
    """A helper function that checks if a item has a skip or a true skip condition.

    Keyword arguments:
    item -- the pytest item object.
    """

    for marker in item.own_markers:
        # If the test is marked with skip then it will not hit the pytest_report_teststatus hook,
        # therefore we need to handle it as skipped here.
        skip_condition = False
        if marker.name == "skipif":
            skip_condition = any(marker.args)
        if marker.name == "skip" or skip_condition:
            return True
    return False


def pytest_sessionfinish(session, exitstatus):
    """A pytest hook that is called after pytest has fulled finished.

    Keyword arguments:
    session -- the pytest session object.
    exitstatus -- the status code of the session.

    Exit code 0: All tests were collected and passed successfully
    Exit code 1: Tests were collected and run but some of the tests failed
    Exit code 2: Test execution was interrupted by the user
    Exit code 3: Internal error happened while executing tests
    Exit code 4: pytest command line usage error
    Exit code 5: No tests were collected
    """
    cwd = pathlib.Path.cwd()
    if SYMLINK_PATH:
        print("Plugin warning[vscode-pytest]: SYMLINK set, adjusting cwd.")
        cwd = pathlib.Path(SYMLINK_PATH)

    if IS_DISCOVERY:
        if not (exitstatus == 0 or exitstatus == 1 or exitstatus == 5):
            errorNode: TestNode = {
                "name": "",
                "path": cwd,
                "type_": "error",
                "children": [],
                "id_": "",
            }
            post_response(os.fsdecode(cwd), errorNode)
        try:
            session_node: Union[TestNode, None] = build_test_tree(session)
            if not session_node:
                raise VSCodePytestError(
                    "Something went wrong following pytest finish, \
                        no session node was created"
                )
            post_response(os.fsdecode(cwd), session_node)
        except Exception as e:
            ERRORS.append(
                f"Error Occurred, traceback: {(traceback.format_exc() if e.__traceback__ else '')}"
            )
            errorNode: TestNode = {
                "name": "",
                "path": cwd,
                "type_": "error",
                "children": [],
                "id_": "",
            }
            post_response(os.fsdecode(cwd), errorNode)
    else:
        if exitstatus == 0 or exitstatus == 1:
            exitstatus_bool = "success"
        else:
            ERRORS.append(
                f"Pytest exited with error status: {exitstatus}, {ERROR_MESSAGE_CONST[exitstatus]}"
            )
            exitstatus_bool = "error"

            execution_post(
                os.fsdecode(cwd),
                exitstatus_bool,
                None,
            )
        # send end of transmission token
    command_type = "discovery" if IS_DISCOVERY else "execution"
    payload: EOTPayloadDict = {"command_type": command_type, "eot": True}
    send_post_request(payload)


def build_test_tree(session: pytest.Session) -> TestNode:
    """Builds a tree made up of testing nodes from the pytest session.

    Keyword arguments:
    session -- the pytest session object.
    """
    session_node = create_session_node(session)
    session_children_dict: Dict[str, TestNode] = {}
    file_nodes_dict: Dict[Any, TestNode] = {}
    class_nodes_dict: Dict[str, TestNode] = {}
    function_nodes_dict: Dict[str, TestNode] = {}

    # Check to see if the global variable for symlink path is set
    if SYMLINK_PATH:
        session_node["path"] = SYMLINK_PATH
        session_node["id_"] = os.fspath(SYMLINK_PATH)

    for test_case in session.items:
        test_node = create_test_node(test_case)
        if hasattr(test_case, "callspec"):  # This means it is a parameterized test.
            function_name: str = ""
            # parameterized test cases cut the repetitive part of the name off.
            parent_part, parameterized_section = test_node["name"].split("[", 1)
            test_node["name"] = "[" + parameterized_section
            parent_path = os.fspath(get_node_path(test_case)) + "::" + parent_part
            try:
                function_name = test_case.originalname  # type: ignore
                function_test_node = function_nodes_dict[parent_path]
            except AttributeError:  # actual error has occurred
                ERRORS.append(
                    f"unable to find original name for {test_case.name} with parameterization detected."
                )
                raise VSCodePytestError("Unable to find original name for parameterized test case")
            except KeyError:
                function_test_node: TestNode = create_parameterized_function_node(
                    function_name, get_node_path(test_case), test_case.nodeid
                )
                function_nodes_dict[parent_path] = function_test_node
            function_test_node["children"].append(test_node)
            # Check if the parent node of the function is file, if so create/add to this file node.
            if isinstance(test_case.parent, pytest.File):
                try:
                    parent_test_case = file_nodes_dict[test_case.parent]
                except KeyError:
                    parent_test_case = create_file_node(test_case.parent)
                    file_nodes_dict[test_case.parent] = parent_test_case
                if function_test_node not in parent_test_case["children"]:
                    parent_test_case["children"].append(function_test_node)
            # If the parent is not a file, it is a class, add the function node as the test node to handle subsequent nesting.
            test_node = function_test_node
        if isinstance(test_case.parent, pytest.Class):
            case_iter = test_case.parent
            node_child_iter = test_node
            test_class_node: Union[TestNode, None] = None
            while isinstance(case_iter, pytest.Class):
                # While the given node is a class, create a class and nest the previous node as a child.
                try:
                    test_class_node = class_nodes_dict[case_iter.nodeid]
                except KeyError:
                    test_class_node = create_class_node(case_iter)
                    class_nodes_dict[case_iter.nodeid] = test_class_node
                # Check if the class already has the child node. This will occur if the test is parameterized.
                if node_child_iter not in test_class_node["children"]:
                    test_class_node["children"].append(node_child_iter)
                # Iterate up.
                node_child_iter = test_class_node
                case_iter = case_iter.parent
            # Now the parent node is not a class node, it is a file node.
            if case_iter:
                parent_module = case_iter
            else:
                ERRORS.append(f"Test class {case_iter} has no parent")
                break
            # Create a file node that has the last class as a child.
            try:
                test_file_node: TestNode = file_nodes_dict[parent_module]
            except KeyError:
                test_file_node = create_file_node(parent_module)
                file_nodes_dict[parent_module] = test_file_node
            # Check if the class is already a child of the file node.
            if test_class_node is not None and test_class_node not in test_file_node["children"]:
                test_file_node["children"].append(test_class_node)
        elif not hasattr(test_case, "callspec"):
            # This includes test cases that are pytest functions or a doctests.
            try:
                parent_test_case = file_nodes_dict[test_case.parent]
            except KeyError:
                parent_test_case = create_file_node(test_case.parent)
                file_nodes_dict[test_case.parent] = parent_test_case
            parent_test_case["children"].append(test_node)
    created_files_folders_dict: Dict[str, TestNode] = {}
    for _, file_node in file_nodes_dict.items():
        # Iterate through all the files that exist and construct them into nested folders.
        root_folder_node: TestNode = build_nested_folders(
            file_node, created_files_folders_dict, session
        )
        # The final folder we get to is the highest folder in the path
        # and therefore we add this as a child to the session.
        root_id = root_folder_node.get("id_")
        if root_id and root_id not in session_children_dict:
            session_children_dict[root_id] = root_folder_node
    session_node["children"] = list(session_children_dict.values())
    return session_node


def build_nested_folders(
    file_node: TestNode,
    created_files_folders_dict: Dict[str, TestNode],
    session: pytest.Session,
) -> TestNode:
    """Takes a file or folder and builds the nested folder structure for it.

    Keyword arguments:
    file_module -- the created module for the file we  are nesting.
    file_node -- the file node that we are building the nested folders for.
    created_files_folders_dict -- Dictionary of all the folders and files that have been created where the key is the path.
    session -- the pytest session object.
    """
    prev_folder_node = file_node

    # Begin the iterator_path one level above the current file.
    iterator_path = file_node["path"].parent
    while iterator_path != get_node_path(session):
        curr_folder_name = iterator_path.name
        try:
            curr_folder_node: TestNode = created_files_folders_dict[os.fspath(iterator_path)]
        except KeyError:
            curr_folder_node: TestNode = create_folder_node(curr_folder_name, iterator_path)
            created_files_folders_dict[os.fspath(iterator_path)] = curr_folder_node
        if prev_folder_node not in curr_folder_node["children"]:
            curr_folder_node["children"].append(prev_folder_node)
        iterator_path = iterator_path.parent
        prev_folder_node = curr_folder_node
    return prev_folder_node


def create_test_node(
    test_case: pytest.Item,
) -> TestItem:
    """Creates a test node from a pytest test case.

    Keyword arguments:
    test_case -- the pytest test case.
    """
    test_case_loc: str = (
        str(test_case.location[1] + 1) if (test_case.location[1] is not None) else ""
    )
    absolute_test_id = get_absolute_test_id(test_case.nodeid, get_node_path(test_case))
    return {
        "name": test_case.name,
        "path": get_node_path(test_case),
        "lineno": test_case_loc,
        "type_": "test",
        "id_": absolute_test_id,
        "runID": absolute_test_id,
    }


def create_session_node(session: pytest.Session) -> TestNode:
    """Creates a session node from a pytest session.

    Keyword arguments:
    session -- the pytest session.
    """
    node_path = get_node_path(session)
    return {
        "name": node_path.name,
        "path": node_path,
        "type_": "folder",
        "children": [],
        "id_": os.fspath(node_path),
    }


def create_class_node(class_module: pytest.Class) -> TestNode:
    """Creates a class node from a pytest class object.

    Keyword arguments:
    class_module -- the pytest object representing a class module.
    """
    return {
        "name": class_module.name,
        "path": get_node_path(class_module),
        "type_": "class",
        "children": [],
        "id_": class_module.nodeid,
    }


def create_parameterized_function_node(
    function_name: str, test_path: pathlib.Path, test_id: str
) -> TestNode:
    """Creates a function node to be the parent for the parameterized test nodes.

    Keyword arguments:
    function_name -- the name of the function.
    test_path -- the path to the test file.
    test_id -- the id of the test, which is a parameterized test so it
      must be edited to get a unique id for the function node.
    """
    function_id: str = test_id.split("::")[0] + "::" + function_name
    return {
        "name": function_name,
        "path": test_path,
        "type_": "function",
        "children": [],
        "id_": function_id,
    }


def create_file_node(file_module: Any) -> TestNode:
    """Creates a file node from a pytest file module.

    Keyword arguments:
    file_module -- the pytest file module.
    """
    node_path = get_node_path(file_module)
    return {
        "name": node_path.name,
        "path": node_path,
        "type_": "file",
        "id_": os.fspath(node_path),
        "children": [],
    }


def create_folder_node(folder_name: str, path_iterator: pathlib.Path) -> TestNode:
    """Creates a folder node from a pytest folder name and its path.

    Keyword arguments:
    folderName -- the name of the folder.
    path_iterator -- the path of the folder.
    """
    return {
        "name": folder_name,
        "path": path_iterator,
        "type_": "folder",
        "id_": os.fspath(path_iterator),
        "children": [],
    }


class DiscoveryPayloadDict(TypedDict):
    """A dictionary that is used to send a post request to the server."""

    cwd: str
    status: Literal["success", "error"]
    tests: Optional[TestNode]
    error: Optional[List[str]]


class ExecutionPayloadDict(Dict):
    """
    A dictionary that is used to send a execution post request to the server.
    """

    cwd: str
    status: Literal["success", "error"]
    result: Union[testRunResultDict, None]
    not_found: Union[List[str], None]  # Currently unused need to check
    error: Union[str, None]  # Currently unused need to check


class EOTPayloadDict(TypedDict):
    """A dictionary that is used to send a end of transmission post request to the server."""

    command_type: Union[Literal["discovery"], Literal["execution"]]
    eot: bool


def get_node_path(node: Any) -> pathlib.Path:
    """
    A function that returns the path of a node given the switch to pathlib.Path.
    It also evaluates if the node is a symlink and returns the equivalent path.
    """
    node_path = getattr(node, "path", None) or pathlib.Path(node.fspath)

    if not node_path:
        raise VSCodePytestError(
            f"Unable to find path for node: {node}, node.path: {node.path}, node.fspath: {node.fspath}"
        )

    # Check for the session node since it has the symlink already.
    if SYMLINK_PATH and not isinstance(node, pytest.Session):
        # Get relative between the cwd (resolved path) and the node path.
        try:
            # check to see if the node path contains the symlink root already
            common_path = os.path.commonpath([SYMLINK_PATH, node_path])
            if common_path == os.fsdecode(SYMLINK_PATH):
                # node path is already relative to the SYMLINK_PATH root therefore return
                return node_path
            else:
                # if the node path is not a symlink, then we need to calculate the equivalent symlink path
                # get the relative path between the cwd and the node path (as the node path is not a symlink)
                rel_path = node_path.relative_to(pathlib.Path.cwd())
                # combine the difference between the cwd and the node path with the symlink path
                sym_path = pathlib.Path(os.path.join(SYMLINK_PATH, rel_path))
                return sym_path
        except Exception as e:
            raise VSCodePytestError(
                f"Error occurred while calculating symlink equivalent from node path: {e}"
                f"\n SYMLINK_PATH: {SYMLINK_PATH}, \n node path: {node_path}, \n cwd: {pathlib.Path.cwd()}"
            )
    return node_path


__writer = None
atexit.register(lambda: __writer.close() if __writer else None)


def execution_post(
    cwd: str, status: Literal["success", "error"], tests: Union[testRunResultDict, None]
):
    """
    Sends a POST request with execution payload details.

    Args:
        cwd (str): Current working directory.
        status (Literal["success", "error"]): Execution status indicating success or error.
        tests (Union[testRunResultDict, None]): Test run results, if available.
    """

    payload: ExecutionPayloadDict = ExecutionPayloadDict(
        cwd=cwd, status=status, result=tests, not_found=None, error=None
    )
    if ERRORS:
        payload["error"] = ERRORS
    send_post_request(payload)


def post_response(cwd: str, session_node: TestNode) -> None:
    """
    Sends a POST request with test session details in payload.

    Args:
        cwd (str): Current working directory.
        session_node (TestNode): Node information of the test session.
    """
    payload: DiscoveryPayloadDict = {
        "cwd": cwd,
        "status": "success" if not ERRORS else "error",
        "tests": session_node,
        "error": [],
    }
    if ERRORS is not None:
        payload["error"] = ERRORS
    send_post_request(payload, cls_encoder=PathEncoder)


class PathEncoder(json.JSONEncoder):
    """A custom JSON encoder that encodes pathlib.Path objects as strings."""

    def default(self, obj):  # type: ignore ReportIncompatibleMethodOverride (remove once updated upstream)
        if isinstance(obj, pathlib.Path):
            return os.fspath(obj)
        return super().default(obj)


def send_post_request(
    payload: Union[ExecutionPayloadDict, DiscoveryPayloadDict, EOTPayloadDict],
    cls_encoder=None,
):
    """
    Sends a post request to the server.

    Keyword arguments:
    payload -- the payload data to be sent.
    cls_encoder -- a custom encoder if needed.
    """
    if not TEST_RUN_PIPE:
        error_msg = (
            "PYTEST ERROR: TEST_RUN_PIPE is not set at the time of pytest starting. "
            "Please confirm this environment variable is not being changed or removed "
            "as it is required for successful test discovery and execution."
            f"TEST_RUN_PIPE = {TEST_RUN_PIPE}\n"
        )
        print(error_msg, file=sys.stderr)
        raise VSCodePytestError(error_msg)

    global __writer

    if __writer is None:
        try:
            __writer = socket_manager.PipeManager(TEST_RUN_PIPE)
            __writer.connect()
        except Exception as error:
            error_msg = f"Error attempting to connect to extension named pipe {TEST_RUN_PIPE}[vscode-pytest]: {error}"
            print(error_msg, file=sys.stderr)
            print(
                "If you are on a Windows machine, this error may be occurring if any of your tests clear environment variables"
                " as they are required to communicate with the extension. Please reference https://docs.pytest.org/en/stable/how-to/monkeypatch.html#monkeypatching-environment-variables"
                "for the correct way to clear environment variables during testing.\n",
                file=sys.stderr,
            )
            __writer = None
            raise VSCodePytestError(error_msg)

    rpc = {
        "jsonrpc": "2.0",
        "params": payload,
    }
    data = json.dumps(rpc, cls=cls_encoder)

    try:
        if __writer:
            __writer.write(data)
        else:
            print(
                f"Plugin error connection error[vscode-pytest], writer is None \n[vscode-pytest] data: \n{data} \n",
                file=sys.stderr,
            )
    except Exception as error:
        print(
            f"Plugin error, exception thrown while attempting to send data[vscode-pytest]: {error} \n[vscode-pytest] data: \n{data}\n",
            file=sys.stderr,
        )
