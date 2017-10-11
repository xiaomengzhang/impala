# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
#
# Module used for executing queries and gathering results.
# The QueryExecutor is meant to be generic and doesn't
# have the knowledge of how to actually execute a query. It takes a query and its config
# and executes is against a executor function.
# For example (in pseudo-code):
#
# def exec_func(query, config):
# ...
#
# config = ImpalaBeeswaxQueryExecConfig()
# executor = QueryExecutor('beeswax', query, config, exec_func)
# executor.run()
# result = executor.result

import logging
import os

from tests.performance.query import Query

# Setup logging for this module.
logging.basicConfig(level=logging.INFO, format='[%(name)s] %(threadName)s: %(message)s')
LOG = logging.getLogger('query_executor')
LOG.setLevel(level=logging.INFO)

# globals.
hive_result_regex = 'Time taken: (\d*).(\d*) seconds'

## TODO: Split executors into their own modules.
class QueryExecConfig(object):
  """Base Class for Execution Configs

  Attributes:
    plugin_runner (PluginRunner?)
  """
  def __init__(self, plugin_runner=None):
    self.plugin_runner = plugin_runner


class ImpalaQueryExecConfig(QueryExecConfig):
  """Base class for Impala query execution config

  Attributes:
    impalad (str): address of impalad <host>:<port>
  """

  def __init__(self, plugin_runner=None, impalad='localhost:21000'):
    super(ImpalaQueryExecConfig, self).__init__(plugin_runner=plugin_runner)
    self._impalad = impalad

  @property
  def impalad(self):
    return self._impalad

  @impalad.setter
  def impalad(self, value):
    self._impalad = value


class JdbcQueryExecConfig(ImpalaQueryExecConfig):
  """Impala query execution config for jdbc

  Attributes:
    tranport (?): ?
  """

  JDBC_CLIENT_PATH = os.path.join(os.environ['IMPALA_HOME'], 'bin/run-jdbc-client.sh')

  def __init__(self, plugin_runner=None, impalad='localhost:21050', transport=None):
    super(JdbcQueryExecConfig, self).__init__(plugin_runner=plugin_runner,
        impalad=impalad)
    self.transport = transport

  @property
  def jdbc_client_cmd(self):
    """The args to run the jdbc client.

    Constructed on the fly, since the impalad it points to can change.
    """
    assert self.transport is not None
    return JdbcQueryExecConfig.JDBC_CLIENT_PATH + ' -i "%s" -t %s' % (self._impalad,
                                                                      self.transport)

class ImpalaHS2QueryConfig(ImpalaQueryExecConfig):
  def __init__(self, use_kerberos=False, impalad="localhost:21050", plugin_runner=None):
    super(ImpalaHS2QueryConfig, self).__init__(plugin_runner=plugin_runner,
        impalad=impalad)
    # TODO Use a config dict for query execution options similar to HS2
    self.use_kerberos = use_kerberos


class HiveHS2QueryConfig(QueryExecConfig):
  def __init__(self,
      plugin_runner=None,
      exec_options = None,
      use_kerberos=False,
      user=None,
      hiveserver='localhost'):
    super(HiveHS2QueryConfig, self).__init__()
    self.exec_options = dict()
    self._build_options(exec_options)
    self.use_kerberos = use_kerberos
    self.user = user
    self.hiveserver = hiveserver

  def _build_options(self, exec_options):
    """Read the exec_options into self.exec_options

    Args:
      exec_options (str): String formatted as "command1;command2"
    """

    if exec_options:
      # exec_options are seperated by ; on the command line
      options = exec_options.split(';')
      for option in options:
        key, value = option.split(':')
        # The keys in HiveService QueryOptions are lower case.
        self.exec_options[key.lower()] = value

class BeeswaxQueryExecConfig(ImpalaQueryExecConfig):
  """Impala query execution config for beeswax

  Args:
    use_kerberos (boolean)
    exec_options (str): String formatted as "opt1:val1;opt2:val2"
    impalad (str): address of impalad <host>:<port>
    plugin_runner (?): ?

  Attributes:
    use_kerberos (boolean)
    exec_options (dict str -> str): execution options
  """

  def __init__(self, use_kerberos=False, exec_options=None, impalad='localhost:21000',
      plugin_runner=None):
    super(BeeswaxQueryExecConfig, self).__init__(plugin_runner=plugin_runner,
        impalad=impalad)
    self.use_kerberos = use_kerberos
    self.exec_options = dict()
    self._build_options(exec_options)

  def _build_options(self, exec_options):
    """Read the exec_options into self.exec_options

    Args:
      exec_options (str): String formatted as "opt1:val1;opt2:val2"
    """

    if exec_options:
      # exec_options are seperated by ; on the command line
      options = exec_options.split(';')
      for option in options:
        key, value = option.split(':')
        # The keys in ImpalaService QueryOptions are upper case.
        self.exec_options[key.upper()] = value


class QueryExecutor(object):
  """Executes a query.

  Args:
    name (str): eg. "hive"
    query (Query): SQL query to be executed
    func (function): Function that accepts a QueryExecOption parameter and returns a
      ImpalaQueryResult. Eg. execute_using_impala_beeswax
    config (QueryExecOption)
    exit_on_error (boolean): Exit right after an error encountered.

  Attributes:
    exec_func (function): Function that accepts a QueryExecOption parameter and returns a
      ImpalaQueryResult.
    exec_config (QueryExecOption)
    query (Query): SQL query to be executed
    exit_on_error (boolean): Exit right after an error encountered.
    executor_name (str): eg. "hive"
    result (ImpalaQueryResult): Contains the result after execute method is called.
  """

  def __init__(self, name, query, func, config, exit_on_error):
    self.exec_func = func
    self.exec_config = config
    self.query = query
    self.exit_on_error = exit_on_error
    self.executor_name = name
    self._result = None

  def prepare(self, impalad):
    """Prepare the query to be run.

    For now, this sets the impalad that the query connects to. If the executor is hive,
    it's a no op.
    """
    if 'hive' not in self.executor_name:
      self.exec_config.impalad = impalad

  def execute(self, plan_first=False):
    """Execute the query using the given execution function.

    If plan_first is true, EXPLAIN the query first so timing does not include the initial
    metadata loading required for planning.
    """
    if plan_first:
      LOG.debug('Planning %s' % self.query)
      assert isinstance(self.query, Query)
      self.query.query_str = 'EXPLAIN ' + self.query.query_str
      try:
        self.exec_func(self.query, self.exec_config)
      finally:
        self.query.query_str = self.query.query_str[len('EXPLAIN '):]
    LOG.debug('Executing %s' % self.query)
    self._result = self.exec_func(self.query, self.exec_config)
    if not self._result.success:
      if self.exit_on_error:
        raise RuntimeError(self._result.query_error)
      else:
        LOG.info("Continuing execution")

  @property
  def result(self):
    """Getter for the result of the query execution.

    A result is a ImpalaQueryResult object that contains the details of a single run of
    the query.
    """
    return self._result