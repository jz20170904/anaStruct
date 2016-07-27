import numpy as np
import math
import copy
from StructuralEngineering.basic import find_closest_index
from StructuralEngineering.trigonometry import Point
import matplotlib.pyplot as plt

"""
The matrices underneath are for slender beams, where the most deformation occurs due to bending.
Shear deformation is not taken into account.
"""


def kinematic_matrix(ai, aj, l):

    return np.array([[-math.cos(ai), math.sin(ai), 0, math.cos(aj), -math.sin(aj), 0],
                     [math.sin(ai) / l, math.cos(ai) / l, -1, -math.sin(aj) / l, -math.cos(aj) / l, 0],
                     [-math.sin(ai) / l, -math.cos(ai) / l, 0, math.sin(aj) / l, math.cos(aj) / l, 1]])


def constitutive_matrix(EA, EI, l):

    return np.array([[EA / l, 0, 0],
                     [0, 4 * EI / l, -2 * EI / l],
                     [0, -2 * EI / l, 4 * EI / l]])


def stiffness_matrix(var_constitutive_matrix, var_kinematic_matrix):

    kinematic_transposed_times_constitutive = np.dot(var_kinematic_matrix.transpose(), var_constitutive_matrix)
    return np.dot(kinematic_transposed_times_constitutive, var_kinematic_matrix)


class SystemElements:
    def __init__(self):
        self.node_ids = []
        self.max_node_id = 2  # minimum is 2, being 1 element
        self.node_objects = []
        self.elements = []
        self.count = 0
        self.system_matrix_locations = []
        self.system_matrix = None
        self.system_force_vector = None
        self.system_displacement_vector = None
        self.shape_system_matrix = None
        self.reduced_force_vector = None
        self.reduced_system_matrix = None
        # list of removed indexes due to conditions
        self.removed_indexes = []
        # list of indexes that remain after conditions are applied
        self.remainder_indexes = []

    def add_element(self, location_list, EA, EI):
        """
        :param location_list: [[x, z], [x, z]]
        :param EA: EA
        :param EI: EI
        :return: Void
        """
        # add the element number
        self.count += 1

        """"
        # add the number of the nodes of the elements

        if len(self.node_ids) == 0:
            self.node_ids.append(1)
            self.node_ids.append(2)

            nodeID1 = 1
            nodeID2 = 2
        else:
            self.node_ids.append(self.node_ids[-1] + 1)

            nodeID1 = self.node_ids[-2]
            nodeID2 = nodeID1 + 1
        """

        point_1 = Point(location_list[0][0], location_list[0][1])
        point_2 = Point(location_list[1][0], location_list[1][1])

        nodeID1 = 1
        nodeID2 = 2
        existing_node1 = False
        existing_node2 = False

        if len(self.elements) != 0:
            count = 1
            for el in self.elements:
                # check if node 1 of the element meets another node. If so, both have the same nodeID
                if el.point_1 == point_1:
                    nodeID1 = el.nodeID1
                    existing_node1 = True
                elif el.point_2 == point_1:
                    nodeID1 = el.nodeID2
                    existing_node1 = True
                elif count == len(self.elements) and existing_node1 is False:
                    self.max_node_id += 1
                    nodeID1 = self.max_node_id

                # check for node 2
                if el.point_1 == point_2:
                    nodeID2 = el.nodeID1
                    existing_node2 = True
                elif el.point_2 == point_2:
                    nodeID2 = el.nodeID2
                    existing_node2 = True
                elif count == len(self.elements) and existing_node2 is False:
                    self.max_node_id += 1
                    nodeID2 = self.max_node_id
                count += 1

        # append the nodes to the system nodes list
        id1 = False
        id2 = False
        for i in self.node_ids:
            if i == nodeID1:
                id1 = True  # nodeID1 allready in system
            if i == nodeID2:
                id2 = True  # nodeID2 allready in system

        if id1 is False:
            self.node_ids.append(nodeID1)
        if id2 is False:
            self.node_ids.append(nodeID2)

        # determine the length of the elements
        point = copy.copy(point_2)
        l = point.subtract_point(point_1).modulus()

        # determine the angle of the element with the global x-axis
        delta_x = point_2.x - point_1.x
        delta_z = point_2.z - point_1.z

        if math.isclose(delta_x, 0, rel_tol=1e-5):
            if delta_z > 0:
                ai = 1.5 * math.pi
            else:
                ai = 0.5 * math.pi
        else:
            ai = -math.atan(delta_z / delta_x)
        # aj = ai

        # add element
        element = Element(self.count, EA, EI, l, ai, ai, point_1, point_2)
        element.node_ids.append(nodeID1)
        element.node_ids.append(nodeID2)
        element.nodeID1 = nodeID1
        element.nodeID2 = nodeID2

        element.node_1 = Nodes(nodeID1)
        element.node_2 = Nodes(nodeID2)
        self.elements.append(element)

        # determine the location of each value of the local stiffness matrix in the global stiffness matrix
        row = (self.node_ids[-2] - 1) * 3 + 1
        global_matrix_location = []

        for i in self.elements[-1].stiffness_matrix:
            column = (self.node_ids[-2] - 1) * 3 + 1
            full_row = []
            for val in range(len(i)):
                full_row.append((row, column))
                column += 1
            global_matrix_location.append(full_row)
            row += 1
        self.system_matrix_locations.append(global_matrix_location)

    def assemble_system_matrix(self):
        """
        Shape of the matrix = n nodes * n d.o.f.
        Shape = n * 3
        :return:
        """
        shape = len(self.node_ids) * 3
        self.shape_system_matrix = shape
        self.system_matrix = np.zeros((shape, shape))

        for i in range(len(self.elements)):

            for row in range(len(self.system_matrix_locations[i])):
                count = 0
                for loc in self.system_matrix_locations[i][row]:
                    self.system_matrix[loc[0]-1][loc[1]-1] += self.elements[i].stiffness_matrix[row][count]
                    count += 1

        # returns True if symmetrical.
        return np.allclose((self.system_matrix.transpose()), self.system_matrix)

    def set_force_vector(self, force_list):
        """
        :param force_list: list containing a tuples with the
        1. number of the node,
        2. the number of the direction (1 = x, 2 = z, 3 = y)
        3. the force
        [(1, 3, 1000)] node=1, direction=3 (y), force=1000
        list may contain multiple tuples
        :return: Vector with forces on the nodes
        """
        if self.system_force_vector is None:
            self.system_force_vector = np.zeros(self.max_node_id * 3)

        for i in force_list:
            # index = number of the node-1 * nd.o.f. + x, or z, or y
            # (x = 1 * i[1], y = 2 * i[1]
            index = (i[0] - 1) * 3 + i[1] - 1
            # force = i[2]
            self.system_force_vector[index] += i[2]
        return self.system_force_vector

    def set_displacement_vector(self, nodes_list):
        """
        :param nodes_list: list containing tuples with
        1.the node
        2. the d.o.f. that is set
        :return: Vector with the displacements of the nodes (If displacement is not known, the value is set
        to NaN)
        """
        if self.system_displacement_vector is None:
            self.system_displacement_vector = np.empty(self.max_node_id * 3)
            self.system_displacement_vector[:] = np.NaN

        for i in nodes_list:
            index = (i[0] - 1) * 3 + i[1] - 1
            self.system_displacement_vector[index] = 0
        return self.system_displacement_vector

    def process_conditions(self):
        original_force_vector = np.array(self.system_force_vector)
        original_system_matrix = np.array(self.system_matrix)
        remove_count = 0
        # remove the unsulvable values from the matrix and vectors
        for i in range(self.shape_system_matrix):
            index = i - remove_count
            if self.system_displacement_vector[index] == 0:
                self.system_displacement_vector = np.delete(self.system_displacement_vector, index, 0)
                self.system_force_vector = np.delete(self.system_force_vector, index, 0)
                self.system_matrix = np.delete(self.system_matrix, index, 0)
                self.system_matrix = np.delete(self.system_matrix, index, 1)
                remove_count += 1
                self.removed_indexes.append(i)
            else:
                self.remainder_indexes.append(i)
        self.reduced_force_vector = self.system_force_vector
        self.reduced_system_matrix = self.system_matrix
        self.system_force_vector = original_force_vector
        self.system_matrix = original_system_matrix

    def solve(self):
        reduced_displacement_vector = np.linalg.solve(self.reduced_system_matrix, self.reduced_force_vector)
        self.system_displacement_vector = np.zeros(self.shape_system_matrix)
        count = 0

        for i in self.remainder_indexes:
            self.system_displacement_vector[i] = reduced_displacement_vector[count]
            count += 1

        # determine the size (=6)  and the indexes of the displacement vector per element
        for i in self.elements:
            max_index = i.node_ids[-1] * 3
            min_index = max_index - 6

            for val in range(6):
                i.element_displacement_vector[val] = self.system_displacement_vector[min_index + val]
                i.determine_force_vector()

        self.node_results()
        return self.system_displacement_vector

    def node_results(self):
        """
        assigns the forces and displacements determined in the system_vectors and the element_vectors to the nodes.
        """

        for el in self.elements:
            el.determine_node_results()

            el.node_1.print()
            el.node_2.print()

    def add_support_hinged(self, nodeID):
        """
        adds a hinged support a the given node
        :param nodeID: integer representing the nodes ID
        """
        self.set_displacement_vector([(nodeID, 1), (nodeID, 2)])

    def add_support_roll(self, nodeID, direction=2):
        """
        adds a rollable support at the given node
        :param nodeID: integer representing the nodes ID
        :param direction: integer representing that is fixed: x = 1, z = 2
        """
        self.set_displacement_vector([(nodeID, direction)])

    def add_support_fixed(self, nodeID):
        """
        adds a fixed support at the given node
        :param nodeID: integer representing the nodes ID
        """
        self.set_displacement_vector([(nodeID, 1), (nodeID, 2), (nodeID, 3)])

    def q_load(self, elementID, q, direction=1):
        """
        :param elementID: integer representing the element ID
        :param direction: 1 = towards the element, -1 = away from the element
        :param q: value of the q-load
        :return:
        """

        for obj in self.elements:
            if obj.ID == elementID:
                element = obj
                break

        element.q_load = q * direction

        # determine the left point for the direction of the primary moment
        left_moment = 1 / 12 * q * element.l**2 * direction
        right_moment = -1 / 12 * q * element.l**2 * direction
        reaction_x = 0.5 * q * element.l * direction * math.sin(element.alpha)
        reaction_z = 0.5 * q * element.l * direction * math.cos(element.alpha)

        # place the primary forces in the 6*6 primary force matrix
        element.element_primary_force_vector[2] += left_moment
        element.element_primary_force_vector[5] += right_moment

        element.element_primary_force_vector[1] -= reaction_z
        element.element_primary_force_vector[4] -= reaction_z
        element.element_primary_force_vector[0] -= reaction_x
        element.element_primary_force_vector[3] -= reaction_x

        # system force vector. System forces = element force * -1
        # first row are the moments
        # second and third row are the reacton forces. The direction
        self.set_force_vector([(element.node_1.ID, 3, -left_moment), (element.node_2.ID, 3, -right_moment),
                               (element.node_1.ID, 2, reaction_z), (element.node_2.ID, 2, reaction_z),
                               (element.node_1.ID, 1, reaction_x), (element.node_2.ID, 1, reaction_x)])

        return self.system_force_vector

    def point_load(self, Fx=0, Fz=0, nodeID=None):

        if nodeID is not None:
            # system force vector.
            self.set_force_vector([(nodeID, 1, Fx), (nodeID, 2, Fz)])

        return self.system_force_vector

    def show_bending_moment(self):
        fig = plt.figure()
        ax = fig.add_subplot(111)
        con = 20

        # determine factor scale by the maximum moment
        max_moment = 0
        for el in self.elements:
            if el.q_load:
                sagging_moment = abs(1 / 8 * -el.q_load * el.l ** 2 + 0.5 * (el.node_1.Ty + el.node_2.Ty))
                if sagging_moment > max_moment:
                    max_moment = sagging_moment

            if abs(el.node_1.Ty) > max_moment:
                max_moment = abs(el.node_1.Ty)
            if abs(el.node_2.Ty) > max_moment:
                max_moment = abs(el.node_2.Ty)

        if math.isclose(max_moment, 0, rel_tol=1e-4) is False:
            factor = 1 / max_moment
        else:
            factor = 0.1

        # determine max value for scaling
        max_val = 0

        for el in self.elements:
            # plot structure
            axis_values = el.plot_values_element()
            x_val = axis_values[0]
            y_val = axis_values[1]
            ax.plot(x_val , y_val, color='black')

            if max(max(x_val ), max(y_val)) > max_val:
                max_val = max(max(x_val ), max(y_val))

            # plot moment
            axis_values = el.plot_values_bending_moment(factor, con)
            x_val = axis_values[0]
            y_val = axis_values[1]
            ax.plot(x_val , y_val, color='b')

            # add value to plot
            ax.text(x_val[1], y_val[1], "%s" % round(abs(el.node_1.Ty), 2))
            ax.text(x_val[-2], y_val[-2], "%s" % round(abs(el.node_2.Ty), 2))

            if el.q_load:
                index = con // 2
                ax.text(x_val[index], y_val[index], "%s" % round(abs(axis_values[2]), 2))

        max_val += 2
        ax.axis([-2, max_val, -2, max_val])
        plt.show()

    def show_normal_forces(self):
        fig = plt.figure()
        ax = fig.add_subplot(111)
        con = 20

        # determine max value for scaling
        max_val = 0

        # determine factor scale by the maximum force
        max_force = 0
        for el in self.elements:
            if abs(el.N) > max_force:

                max_force = abs(el.N)
            if abs(el.N) > max_force:
                max_force = abs(el.N)

        if math.isclose(max_force, 0):
            factor = 0.1
        else:
            factor = 1 / max_force

        for el in self.elements:
            # plot structure
            axis_values = el.plot_values_element()
            x_val = axis_values[0]
            y_val = axis_values[1]
            ax.plot(x_val , y_val, color='black')

            if max(max(x_val ), max(y_val)) > max_val:
                max_val = max(max(x_val ), max(y_val))

            # plot force
            axis_values = el.plot_values_normal_force(factor)
            x_val = axis_values[0]
            y_val = axis_values[1]
            ax.plot(x_val, y_val, color='b')

            # add value to plot
            ax.text(x_val[1], y_val[1], "%s" % round(el.N, 2))
            ax.text(x_val[-2], y_val[-2], "%s" % round(el.N, 2))

        max_val += 2
        ax.axis([-2, max_val, -2, max_val])
        plt.show()


class Element:
    def __init__(self, ID, EA, EI, l, ai, aj, point_1, point_2):
        """
        :param ID: integer representing the elements ID
        :param EA: Young's modulus * Area
        :param EI: Young's modulus * Moment of Inertia
        :param l: length
        :param ai: angle between element and x-axis
        :param aj: = ai
        :param point_1: point object
        :param point_2: point object
        """
        self.ID = ID
        self.EA = EA
        self.EI = EI
        self.l = l
        self.point_1 = point_1
        self.point_2 = point_2
        self.alpha = ai
        self.kinematic_matrix = kinematic_matrix(ai, aj, l)
        self.constitutive_matrix = constitutive_matrix(EA, EI, l)
        self.stiffness_matrix = stiffness_matrix(self.constitutive_matrix, self.kinematic_matrix)
        self.nodeID1 = None
        self.nodeID2 = None
        self.node_ids = []
        self.node_1 = None
        self.node_2 = None
        self.element_displacement_vector = np.empty(6)
        self.element_primary_force_vector = np.zeros(6)
        self.element_force_vector = None
        self.q_load = None
        self.N = None

    def determine_force_vector(self):
        self.element_force_vector = np.dot(self.stiffness_matrix, self.element_displacement_vector)

        return self.element_force_vector

    def determine_node_results(self):
        self.node_1 = Nodes(
            ID=self.node_ids[0],
            Fx=self.element_force_vector[0] + self.element_primary_force_vector[0],
            Fz=self.element_force_vector[1] + self.element_primary_force_vector[1],
            Ty=self.element_force_vector[2] + self.element_primary_force_vector[2],
            ux=self.element_displacement_vector[0],
            uz=self.element_displacement_vector[1],
            phiy=self.element_displacement_vector[2],
        )

        self.node_2 = Nodes(
            ID=self.node_ids[1],
            Fx=self.element_force_vector[3] + self.element_primary_force_vector[3],
            Fz=self.element_force_vector[4] + self.element_primary_force_vector[4],
            Ty=self.element_force_vector[5] + self.element_primary_force_vector[5],
            ux=self.element_displacement_vector[3],
            uz=self.element_displacement_vector[4],
            phiy=self.element_displacement_vector[5]
        )
        self.determine_normal_force()

    def determine_normal_force(self):
        dx = self.point_1.x - self.point_2.x

        if math.isclose(dx, 0):  # element is vertical
            if self.point_1.z < self.point_2.z:  # point 1 is bottom
                self.N = -self.node_1.Fz  # compression and tension in opposite direction
            else:
                self.N = self.node_1.Fz  # compression and tension in opposite direction

        elif math.isclose(self.alpha, 0):  # element is horizontal
            if self.point_1.x < self.point_2.x:  # point 1 is left
                self.N = -self.node_1.Fx  # compression and tension in good direction
            else:
                self.N = self.node_1.Fx  # compression and tension in opposite direction

        else:
            if math.cos(self.alpha) > 0:
                if self.point_1.x < self.point_2.x:  # point 1 is left
                    if self.node_1.Fx > 0:  # compression in element
                        self.N = -math.sqrt(self.node_1.Fx**2 + self.node_1.Fz**2)
                    else:
                        self.N = math.sqrt(self.node_1.Fx ** 2 + self.node_1.Fz ** 2)
                else:  # point 1 is right
                    if self.node_1.Fx < 0:  # compression in element
                        self.N = -math.sqrt(self.node_1.Fx ** 2 + self.node_1.Fz ** 2)
                    else:
                        self.N = math.sqrt(self.node_1.Fx ** 2 + self.node_1.Fz ** 2)

    def plot_values_normal_force(self, factor):
        x1 = self.point_1.x
        y1 = -self.point_1.z
        x2 = self.point_2.x
        y2 = -self.point_2.z

        x_1 = x1 + self.N * math.cos(0.5 * math.pi + self.alpha) * factor
        y_1 = y1 + self.N * math.sin(0.5 * math.pi + self.alpha) * factor
        x_2 = x2 + self.N * math.cos(0.5 * math.pi + self.alpha) * factor
        y_2 = y2 + self.N * math.sin(0.5 * math.pi + self.alpha) * factor

        x_val = [x1, x_1, x_2, x2]
        y_val = [y1, y_1, y_2, y2]
        return x_val, y_val

    def plot_values_element(self):
        x_val = [self.point_1.x, self.point_2.x]
        y_val = [-self.point_1.z, -self.point_2.z]
        return x_val, y_val, self.ID

    def plot_values_bending_moment(self, factor, con):
        """
        :param factor: scaling the plot
        :param con: amount of x-values
        :return:
        """

        # plot the bending moment
        x1 = self.point_1.x
        y1 = -self.point_1.z
        x2 = self.point_2.x
        y2 = -self.point_2.z
        dx = x2 - x1
        dy = y2 - y1

        if math.isclose(self.alpha, 0.5 * math.pi, rel_tol=1e-4) or\
                math.isclose(self.alpha, 1.5 * math.pi, rel_tol=1e-4):
            # point 1 is bottom
            x_1 = x1 + self.node_1.Ty * math.cos(0.5 * math.pi + self.alpha) * factor
            y_1 = y1 + self.node_1.Ty * math.sin(0.5 * math.pi + self.alpha) * factor
            x_2 = x2 - self.node_2.Ty * math.cos(0.5 * math.pi + self.alpha) * factor
            y_2 = y2 - self.node_2.Ty * math.sin(0.5 * math.pi + self.alpha) * factor

        else:
            if dx > 0:  # point 1 = left and point 2 is right
                # With a negative moment (at support), left is positive and right is negative
                # node 1 is left, node 2 is right
                x_1 = x1 + self.node_1.Ty * math.cos(0.5 * math.pi + self.alpha) * factor
                y_1 = y1 + self.node_1.Ty * math.sin(0.5 * math.pi + self.alpha) * factor
                x_2 = x2 - self.node_2.Ty * math.cos(0.5 * math.pi + self.alpha) * factor
                y_2 = y2 - self.node_2.Ty * math.sin(0.5 * math.pi + self.alpha) * factor
            else:
                # node 1 is right, node 2 is left
                x_1 = x1 - self.node_1.Ty * math.cos(0.5 * math.pi + self.alpha) * factor
                y_1 = y1 - self.node_1.Ty * math.sin(0.5 * math.pi + self.alpha) * factor
                x_2 = x2 + self.node_2.Ty * math.cos(0.5 * math.pi + self.alpha) * factor
                y_2 = y2 + self.node_2.Ty * math.sin(0.5 * math.pi + self.alpha) * factor

        x_val = np.linspace(0, 1, con)
        y_val = np.empty(con)
        dx = x_2 - x_1
        dy = y_2 - y_1
        count = 0

        for i in x_val:
            x_val[count] = x_1 + i * dx
            y_val[count] = y_1 + i * dy

            if self.q_load:
                x = i * self.l
                q_part = (-0.5 * -self.q_load * x**2 + 0.5 * -self.q_load * self.l * x)

                y_val[count] += math.cos(self.alpha) * q_part * factor
            count += 1

        x_val = np.append(x_val, x2)
        y_val = np.append(y_val, y2)
        x_val = np.insert(x_val, 0, x1)
        y_val = np.insert(y_val, 0, y1)

        if self.q_load:
            sagging_moment = (-self.node_1.Ty + self.node_2.Ty) * 0.5 + 0.125 * self.q_load * self.l**2
            return x_val, y_val, sagging_moment
        else:
            return x_val, y_val


class Nodes:
    def __init__(self, ID, Fx=0, Fz=0, Ty=0, ux=0, uz=0, phiy=0):
        self.ID = ID
        # forces
        self.Fx = Fx
        self.Fz = Fz
        self.Ty = Ty
        # displacements
        self.ux = ux
        self.uz = uz
        self.phiy = phiy

    def __sub__(self, other):
        Fx = self.Fx - other.Fx
        Fz = self.Fz - other.Fz
        Ty = self.Ty - other.Ty
        ux = self.ux - other.ux
        uz = self.uz - other.uz
        phiy = self.phiy - other.phiy

        return Nodes(self.ID, Fx, Fz, Ty, ux, uz, phiy)

    def print(self):
        print("\nID = %s\n"
              "Fx = %s\n"
              "Fz = %s\n"
              "Ty = %s\n"
              "ux = %s\n"
              "uz = %s\n"
              "phiy = %s" % (self.ID, self.Fx, self.Fz, self.Ty, self.ux, self.uz, self.phiy))

