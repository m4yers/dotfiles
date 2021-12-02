#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Dependency topology helper.
"""

import argparse
import functools
import sys
import re
import os

import networkx as nx

INSTALLER = 'install.sh'
RE_DEPENDS = re.compile(r'^.*#\s*depends-on\s*:(?P<names>.*)$')
RE_SATISFIES = re.compile(r'^.*#\s*satisfies\s*:(?P<names>.*)$')

def read_dependencies(filename):
  """Find dependency or satisfying list of an installer.

  Functions looks for two string patters:
    - # depends-on: <list>
    - # satisfies:  <list>
  The former one defines dependencies of an installer, the latter defines
  dependencies this installer provides for others.

  Args:
    filename: An installer full name.

  Returns:
    A tuple, where the first element is True if the second element defines
    dependencies, and False if it defines satisfying list.
  """
  depends = list()
  satisfies = list()
  with open(filename, 'r') as handler:
    dep_or_sat = True
    for line in handler.readlines():
      match = RE_DEPENDS.match(line)
      if not match:
        match = RE_SATISFIES.match(line)
        if not match:
          continue
        dep_or_sat = False

      names = match.groupdict().get('names', '')
      names = names.split(',')
      names = list(map(str.rstrip, names))
      names = list(map(str.lstrip, names))
      if dep_or_sat:
        depends.extend(names)
      else:
        satisfies.extend(names)

  return depends, satisfies

def find_topological_order(directory, target=None):
  graph = nx.DiGraph()

  # First, walk the installers and find real providers
  for root, _, files in os.walk(directory):
    if INSTALLER in files:
      name = os.path.basename(root)
      graph.add_node(name, transitive=False)

  # Second, find all dependees and dependers
  for root, _, files in os.walk(directory):
    if INSTALLER in files:
      name = os.path.basename(root)
      dependencies, satisfies = read_dependencies(os.path.join(root, INSTALLER))

      for dependence in dependencies:
        # If by now the dependence does not have a node it does not have a real
        # provider, so we assume it is transitive, i.d. provided by something
        # with different name
        if not graph.has_node(dependence):
          graph.add_node(dependence, transitive=True)

      # Set edge from dependee to its provider
      add_edge = functools.partial(lambda a,b: graph.add_edge(b,a), name)
      list(map(add_edge, dependencies))

      for sat in satisfies:
        # If there is something that tries to satisfy already satisfied
        # dependency we consider this an error
        if graph.has_node(sat) and len(list(graph.predecessors(sat))):
          print(("{} tries to satisfy already existing installer {}".format(name, sat)))
          return False, None
        graph.add_node(sat, transitive=True)

      # Set edge from transitive provider to its real provider
      add_edge = functools.partial(lambda a,b: graph.add_edge(a,b), name)
      list(map(add_edge, satisfies))

  # print graph.edges()
  # sys.exit(0)

  # Not all dependencies are provided by installers of the same name. By
  # collapsing the graph on these 'satisfying' dependencies we point a dependee
  # to a right installer.
  nodes_to_remove = list()
  for node, transitive in graph.nodes(data='transitive'):
    if not transitive:
      continue

    dependees = list(graph.successors(node))
    providers = list(graph.predecessors(node))
    assert len(providers) == 1, 'Must be exactly one provider, node: {}, dependees: {}, providers: {}'.format(node, dependees, providers)

    # Remove transitive node with all its edges
    nodes_to_remove.append(node)

    # Reconnect the graph
    add_edge = functools.partial(graph.add_edge, providers[0])
    list(map(add_edge, dependees))

  for node in nodes_to_remove:
    graph.remove_node(node)

  if not nx.is_directed_acyclic_graph(graph):
    print(("Found dependency cycle: {}".format(nx.find_cycle(graph))))
    return False, None

  if target:
    closure = set([target])
    while True:
      new = closure | set(sum(list(map(list, list(map(graph.predecessors, closure)))), []))
      if closure == new:
        break
      closure = new
    return True, list(nx.topological_sort(graph.subgraph(closure)))

  return True, list(nx.topological_sort(graph))

def create_menu():
  parser = argparse.ArgumentParser(prog='Topo')
  parser.add_argument('directory', metavar='DIR')
  parser.add_argument('--for', dest='target', default=None)
  return parser

def main():
  parser = create_menu()
  options = parser.parse_args()

  success, order = find_topological_order(options.directory, options.target)
  if not success:
    sys.exit(1)

  print((' '.join(order)))
  sys.exit(0)

if __name__ == "__main__":
  main()
