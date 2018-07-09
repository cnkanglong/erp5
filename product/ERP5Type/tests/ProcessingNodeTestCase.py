# -*- coding: utf-8 -*-
import base64, errno, os, select, socket, sys, time
from threading import Thread
from UserDict import IterableUserDict
import Lifetime
from AccessControl.SecurityManagement import (
  newSecurityManager,
  setSecurityManager,
  getSecurityManager,
)
import transaction
from Testing import ZopeTestCase
from ZODB.POSException import ConflictError
from zLOG import LOG, ERROR
from Products.CMFActivity.Activity.Queue import VALIDATION_ERROR_DELAY
from Products.ERP5Type.tests.utils import addUserToDeveloperRole
from Products.ERP5Type.tests.utils import createZServer
from Products.CMFActivity.ActivityTool import getCurrentNode, Message


class DictPersistentWrapper(IterableUserDict, object):

  def __metaclass__(name, base, d):
    def wrap(attr):
      wrapped = getattr(base[0], attr)
      def wrapper(self, *args, **kw):
        self._persistent_object._p_changed = 1
        return wrapped(self, *args, **kw)
      wrapper.__name__ = attr
      return wrapper
    for attr in ('clear', 'setdefault', 'update', '__setitem__', '__delitem__'):
      d[attr] = wrap(attr)
    return type(name, base, d)

  def __init__(self, dict, persistent_object):
    self.data = dict
    self._persistent_object = persistent_object

class ActivityFailed(RuntimeError):
  def __init__(self, activity_list, last_error):
    self.activity_list = activity_list
    self.last_error = last_error
    super(ActivityFailed, self).__init__()

  def __str__(self):
    return 'tic is looping forever. These messages are pending: %r\n%s' % (
      [
         ('/'.join(m.object_path), m.method_id, m.processing_node, m.retry)
         for m in self.activity_list
      ],
      self.last_error,
    )

def patchActivityTool():
  """Redefine several methods of ActivityTool for unit tests
  """
  from Products.CMFActivity.ActivityTool import ActivityTool
  def patch(function):
    name = function.__name__
    orig_function = getattr(ActivityTool, name)
    setattr(ActivityTool, '_orig_' + name, orig_function)
    setattr(ActivityTool, name, function)
    function.__doc__ = orig_function.__doc__
    # make life easier when inspecting the wrapper with ipython
    function._original = orig_function

  # When a ZServer can't be started, the node name ends with ':' (no port).
  @patch
  def _isValidNodeName(self, node_name):
    return True

  # Divert location to register processing and distributing nodes.
  # Load balancing is configured at the root instead of the activity tool,
  # so that additional can register even if there is no portal set up yet.
  # Properties at the root are:
  # - 'test_processing_nodes' to list processing nodes
  # - 'test_distributing_node' to select the distributing node
  @patch
  def getNodeDict(self):
    app = self.getPhysicalRoot()
    if getattr(app, 'test_processing_nodes', None) is None:
      app.test_processing_nodes = {}
    return DictPersistentWrapper(app.test_processing_nodes, app)

  @patch
  def getDistributingNode(self):
    return getattr(self.getPhysicalRoot(), 'test_distributing_node', '')

  # A property to catch setattr on 'distributingNode' would not work
  # because self would lose all acquisition wrappers.
  class SetDistributingNodeProxy(object):
    def __init__(self, ob):
      self._ob = ob
    def __getattr__(self, attr):
      m = getattr(self._ob, attr).im_func
      return lambda *args, **kw: m(self, *args, **kw)
  @patch
  def manage_setDistributingNode(self, distributingNode, REQUEST=None):
    proxy = SetDistributingNodeProxy(self)
    proxy._orig_manage_setDistributingNode(distributingNode, REQUEST=REQUEST)
    self.getPhysicalRoot().test_distributing_node = proxy.distributingNode

  # When there is more than 1 node, prevent the distributing node from
  # processing activities.
  @patch
  def tic(self, processing_node=1, force=0):
    processing_node_list = self.getProcessingNodeList()
    if len(processing_node_list) > 1 and \
       getCurrentNode() == self.getDistributingNode():
      # Sleep between each distribute.
      time.sleep(0.3)
      transaction.commit()
      transaction.begin()
    else:
      self._orig_tic(processing_node, force)


def Application_resolveConflict(self, old_state, saved_state, new_state):
  """Solve conflicts in case several nodes register at the same time
  """
  new_state = new_state.copy()
  old, saved, new = [set(state.pop('test_processing_nodes', {}).items())
                     for state in old_state, saved_state, new_state]
  # The value of these attributes don't have proper __eq__ implementation.
  for attr in '__before_traverse__', '__before_publishing_traverse__':
    del old_state[attr], saved_state[attr]
  if sorted(old_state.items()) != sorted(saved_state.items()):
    raise ConflictError
  new |= saved - old
  new -= old - saved
  new_state['test_processing_nodes'] = nodes = dict(new)
  if len(nodes) != len(new):
    raise ConflictError
  return new_state

from OFS.Application import Application
Application._p_resolveConflict = Application_resolveConflict


class ProcessingNodeTestCase(ZopeTestCase.TestCase):
  """Minimal ERP5 TestCase class to process activities

  When a processing node starts, the portal may not exist yet, or its name is
  unknown, so an additional 'test_portal_name' property at the root is set by
  the node running the unit tests to tell other nodes on which portal activities
  should be processed.
  """

  @staticmethod
  def asyncore_loop():
    try:
      Lifetime.lifetime_loop()
    except KeyboardInterrupt:
      pass
    Lifetime.graceful_shutdown_loop()

  def startZServer(self, verbose=False):
    """Start HTTP ZServer in background"""
    utils = ZopeTestCase.utils
    if utils._Z2HOST is None:
      from Products.ERP5Type.tests.runUnitTest import tests_home
      log = os.path.join(tests_home, "Z2.log")
      _print = lambda hs: verbose and ZopeTestCase._print(
        "Running %s server at %s:%s\n" % (
          hs.server_protocol, hs.server_name, hs.server_port))
      try:
        hs = createZServer(log)
      except RuntimeError, e:
        ZopeTestCase._print(str(e))
      else:
        utils._Z2HOST, utils._Z2PORT = hs.server_name, hs.server_port
        _print(hs)
        try:
          _print(createZServer(log, zserver_type='webdav'))
        except RuntimeError, e:
          ZopeTestCase._print(str(e))
        t = Thread(target=Lifetime.loop)
        t.setDaemon(1)
        t.start()
    return utils._Z2HOST, utils._Z2PORT

  def _registerNode(self, distributing, processing):
    """Register node to process and/or distribute activities"""
    try:
      activity_tool = self.portal.portal_activities
    except AttributeError:
      from Products.CMFActivity.ActivityTool import ActivityTool
      activity_tool = ActivityTool().__of__(self.app)
    currentNode = getCurrentNode()
    if distributing:
      activity_tool.manage_setDistributingNode(currentNode)
    elif currentNode == activity_tool.getDistributingNode():
      activity_tool.manage_setDistributingNode('')
    if processing:
      activity_tool.manage_addToProcessingList((currentNode,))
    else:
      activity_tool.manage_delNode((currentNode,))

  @classmethod
  def unregisterNode(cls):
    if ZopeTestCase.utils._Z2HOST is not None:
      self = cls('unregisterNode')
      self.app = self._app()
      self._registerNode(distributing=0, processing=0)
      transaction.commit()
      self._close()

  def _getLastError(self):
    error_log = self.portal.error_log._getLog()
    if len(error_log):
      return (
        'Last error message:\n'
        '%(type)s\n'
        '%(value)s\n'
        '%(tb_text)s' % error_log[-1]
      )

  def assertNoPendingMessage(self):
    """Get the last error message from error_log"""
    message_list = self.portal.portal_activities.getMessageList()
    if message_list:
      error_message = 'These messages are pending: %r' % [
          ('/'.join(m.object_path), m.method_id, m.processing_node, m.retry)
          for m in message_list]
      last_error = self._getLastError()
      if last_error:
        error_message += '\n' + last_error
      self.fail(error_message)

  def abort(self):
    transaction.begin()
    # Consider reaccessing the portal to trigger a call to ERP5Site.__of__

  def commit(self):
    transaction.commit()
    self.abort()

  def tic(self, verbose=0, stop_condition=lambda message_list: False):
    """Execute pending activities"""
    transaction.commit()
    # Some tests like testDeferredStyle require that we use self.getPortal()
    # instead of self.portal in order to setup current skin.
    portal = self.getPortal()
    portal_activities = portal.portal_activities
    if verbose:
      ZopeTestCase._print('Executing pending activities ...')
      start = time.time()
    getMessageList = portal_activities.getMessageList
    pre_failed_uid_set = {
      x.uid
      for x in getMessageList()
      if x.processing_node < -1
    }
    portal.changeSkin(None)
    old_sm = getSecurityManager()
    old_Message_load = Message.load
    def Message_load(s, **kw):
      """
      Prevent activity retries, as activities must succeed from the first try
      in a unit test environment.
      This is to catch missing activity dependencies which only work because
      activities are being retried until they eventually succeed.
      """
      kw['max_retry'] = 0
      kw['conflict_retry'] = False
      return old_Message_load(s, **kw)
    try:
      Message.load = staticmethod(Message_load)
      newSecurityManager(None, portal.portal_catalog.getWrappedOwner())
      while True:
        if verbose:
          ZopeTestCase._print(' %i' % len(getMessageList()))
        # Put everything in the past - hopefully no activity will have been
        # pushed that far in the future.
        portal_activities.timeShift(30 * VALIDATION_ERROR_DELAY)
        portal_activities.distribute()
        portal_activities.tic()
        self.commit()
        message_list = getMessageList()
        if not message_list or stop_condition(message_list):
          break
        failed_message_set = [
          x
          for x in message_list
          if x.processing_node < -1
        ]
        if failed_message_set:
          raise ActivityFailed(failed_message_set, self._getLastError())
    finally:
      Message.load = staticmethod(old_Message_load)
      setSecurityManager(old_sm)
    if verbose:
      ZopeTestCase._print(' done (%.3fs)\n' % (time.time() - start))
    self.commit()

  def afterSetUp(self):
    """Initialize a node that will only process activities"""
    self.startZServer()
    # Make sure to still have possibilities to edit components
    addUserToDeveloperRole('ERP5TypeTestCase')
    from Zope2.custom_zodb import cluster
    self._registerNode(distributing=not cluster, processing=1)
    self.commit()

  def processing_node(self):
    """Main loop for nodes that process activities"""
    try:
      while not Lifetime._shutdown_phase:
        time.sleep(.3)
        transaction.begin()
        try:
          portal = self.app[self.app.test_portal_name]
        except (AttributeError, KeyError):
          continue
        try:
          portal.portal_activities.process_timer(None, None)
        except Exception:
          LOG('Invoking Activity Tool', ERROR, '', error=sys.exc_info())
    except KeyboardInterrupt:
      pass
