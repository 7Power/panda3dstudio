from ...base import *


class PolygonCreationBase(BaseObject):

    def prepare_poly_creation(self):

        # Make the vertices pickable at polygon level instead of the polygons, to
        # assist with polygon creation

        picking_mask = Mgr.get("picking_mask")
        geom_roots = self._geom_roots
        geom_roots["vert"].show_through(picking_mask)
        geom_roots["poly"].show(picking_mask)

    def init_poly_creation(self):

        geom_roots = self._geom_roots
        render_mask = Mgr.get("render_mask")

        # Create temporary geometry

        tmp_geoms = {}
        tmp_data = {"geoms": tmp_geoms}

        vertex_format_vert = GeomVertexFormat.get_v3()
        vertex_data_vert = GeomVertexData(
            "vert_data", vertex_format_vert, Geom.UH_dynamic)
        vertex_format_line = GeomVertexFormat.get_v3c4()
        vertex_data_line = GeomVertexData(
            "line_data", vertex_format_line, Geom.UH_dynamic)
        vertex_format_tri = GeomVertexFormat.get_v3n3()
        vertex_data_tri = GeomVertexData(
            "tri_data", vertex_format_tri, Geom.UH_dynamic)

        # Create the first vertex of the first triangle

        vertex_data_tri.set_num_rows(1)
        pos_writer = GeomVertexWriter(vertex_data_tri, "vertex")
        pos_writer.add_data3f(0., 0., 0.)
        normal_writer = GeomVertexWriter(vertex_data_tri, "normal")
        normal_writer.add_data3f(0., 0., 0.)

        # Create a temporary geom for new vertices

        points_prim = GeomPoints(Geom.UH_static)
        point_geom = Geom(vertex_data_vert)
        point_geom.add_primitive(points_prim)
        geom_node = GeomNode("new_vertices_geom")
        geom_node.add_geom(point_geom)
        new_vert_geom = geom_roots["vert"].attach_new_node(geom_node)
        new_vert_geom.set_color(1., 1., 0., 1.)
        tmp_geoms["vert"] = new_vert_geom

        # Create a temporary geom for edges

        lines_prim = GeomLines(Geom.UH_static)
        lines_geom = Geom(vertex_data_line)
        lines_geom.add_primitive(lines_prim)
        geom_node = GeomNode("edges_geom")
        geom_node.add_geom(lines_geom)
        edge_geom = geom_roots["subobj"].attach_new_node(geom_node)
        edge_geom.show_through(render_mask)
        edge_geom.set_render_mode_thickness(3)
        edge_geom.set_color_off()
        edge_geom.set_light_off()
        edge_geom.set_texture_off()
        edge_geom.set_material_off()
        edge_geom.set_shader_off()
        tmp_geoms["edge"] = edge_geom
        edge_geom.set_attrib(DepthTestAttrib.make(RenderAttrib.M_less_equal))
        edge_geom.set_bin("background", 1)

        # Create a temporary geom for the new polygon

        tris_prim = GeomTriangles(Geom.UH_static)
        geom = Geom(vertex_data_tri)
        geom.add_primitive(tris_prim)
        geom_node = GeomNode("new_polygon_geom")
        geom_node.add_geom(geom)
        new_poly_geom = geom_roots["poly"].attach_new_node(geom_node)
        tmp_geoms["poly"] = new_poly_geom

        # store all temporary normals of the polygon
        tmp_data["normals"] = [Vec3()]

        # store the indices of the shared vertices for every new triangle
        tmp_data["shared_verts"] = []

        # store the already existing vertices of this GeomDataObject that the new
        # polygon will be merged with (these have to be MergedVertex objects)
        tmp_data["owned_verts"] = {}

        # store the positions of all vertices that the new polygon will contain
        tmp_data["vert_pos"] = []

        # store the vertex geom row indices
        tmp_data["vert_geom_rows"] = []

        # store the indices of all vertices that the new polygon will contain, in
        # the winding order needed to correctly define the normals and visibility of
        # the triangles
        tmp_data["vert_indices"] = [[0, 1, 2]]

        # store the index of the first vertex to be used to define the next triangle;
        # that vertex will be used together with the other shared vertex and the one
        # currently under the mouse
        tmp_data["start_index"] = 0
        tmp_data["start_index_prev"] = 0

        # keep track of whether or not the normal of the new polygon will be flipped,
        # relative to the automatically computed direction
        tmp_data["flip_normal"] = False

        self._tmp_data = tmp_data

    def add_new_poly_vertex(self, vertex=None, point=None):

        tmp_data = self._tmp_data

        last_index = len(tmp_data["vert_pos"])

        if vertex:

            vert_id = vertex.get_id()

            if vert_id in self._subobjs["vert"]:

                merged_vert = self._merged_verts[vert_id]

                if merged_vert.is_border_vertex():
                    tmp_data["owned_verts"][last_index] = merged_vert

                pos = vertex.get_pos()

            else:

                pos = vertex.get_pos(self._origin)

        else:

            grid_origin = Mgr.get(("grid", "origin"))
            pos = self._origin.get_relative_point(grid_origin, point)

            geom = tmp_data["geoms"]["vert"].node().modify_geom(0)
            vertex_data = geom.modify_vertex_data()
            row = vertex_data.get_num_rows()
            pos_writer = GeomVertexWriter(vertex_data, "vertex")
            pos_writer.set_row(row)
            pos_writer.add_data3f(pos)
            point_prim = geom.modify_primitive(0)
            point_prim.add_vertex(row)
            tmp_data["vert_geom_rows"].append(last_index)

        tmp_data["vert_pos"].append(pos)

        geom = tmp_data["geoms"]["poly"].node().modify_geom(0)
        vertex_data = geom.modify_vertex_data()
        pos_writer = GeomVertexWriter(vertex_data, "vertex")
        pos_writer.set_row(last_index)
        pos_writer.set_data3f(pos)
        pos_writer.add_data3f(pos)
        normal_writer = GeomVertexWriter(vertex_data, "normal")
        normal_writer.set_row(last_index)
        normal_writer.set_data3f(0., 0., 0.)
        normal_writer.add_data3f(0., 0., 0.)

        if last_index == 1:

            if tmp_data["flip_normal"]:
                geom.reverse_in_place()

            tris_prim = geom.modify_primitive(0)
            tris_prim.add_next_vertices(3)

            if tmp_data["flip_normal"]:
                geom.reverse_in_place()

        elif last_index > 1:

            start_index = tmp_data["start_index"]
            index2 = last_index - 1 if start_index == last_index else last_index
            index3 = last_index + 1
            tmp_data["shared_verts"].append(
                [start_index, tmp_data["start_index_prev"]])
            prev_indices = tmp_data["vert_indices"][-1]
            i1 = prev_indices.index(start_index)
            i2 = prev_indices.index(index2)

            # to obtain the correct normal and visibility of the new triangle (so it
            # appears to form a contiguous surface with the previous triangle), the
            # indices of the vertices that define the edge shared with the previously
            # created triangle need to be used in reverse order (because these vertices
            # are used with a new third vertex that lies on the other side of the
            # shared edge, compared to the third vertex of the previous
            # triangle)
            if abs(i2 - i1) == 1:
                indices = [prev_indices[max(i1, i2)], prev_indices[
                    min(i1, i2)], index3]
            else:
                # the indices were not listed consecutively; since there are only 3
                # indices in the list, this means that, if the list were to be rotated,
                # they *would* follow each other directly, with their order reversed, so
                # they are already in the needed order
                indices = [prev_indices[min(i1, i2)], prev_indices[
                    max(i1, i2)], index3]

            tmp_data["vert_indices"].append(indices)

            if tmp_data["flip_normal"]:
                geom.reverse_in_place()

            tris_prim = geom.modify_primitive(0)
            tris_prim.add_vertices(*indices)

            if tmp_data["flip_normal"]:
                geom.reverse_in_place()

            pos1, pos2, pos3 = [tmp_data["vert_pos"][i] for i in prev_indices]
            normal = V3D(pos2 - pos1) ** V3D(pos3 - pos2)
            normal += tmp_data["normals"][-1]

            tmp_data["normals"].append(Vec3(normal))
            normal.normalize()

            if tmp_data["flip_normal"]:
                normal *= -1.

            normal_writer.set_row(0)

            for i in range(last_index):
                normal_writer.set_data3f(normal)

        edge_geom = tmp_data["geoms"]["edge"].node().modify_geom(0)
        vertex_data = edge_geom.modify_vertex_data()
        count = vertex_data.get_num_rows()
        pos_writer = GeomVertexWriter(vertex_data, "vertex")
        pos_writer.set_row(count)
        col_writer = GeomVertexWriter(vertex_data, "color")
        col_writer.set_row(count)
        edge_prim = edge_geom.modify_primitive(0)

        if last_index:
            start_index = tmp_data["start_index"]
            index2 = last_index - 1 if start_index == last_index else last_index
            start_pos = tmp_data["vert_pos"][start_index]
            pos2 = tmp_data["vert_pos"][index2]
            pos_writer.add_data3f(start_pos)
            pos_writer.add_data3f(pos)
            pos_writer.add_data3f(pos2)
            pos_writer.add_data3f(pos)
            col_writer.add_data4f(.5, .5, .5, 1.)
            col_writer.add_data4f(.5, .5, .5, 1.)
            col_writer.add_data4f(1., 1., 0., 1.)
            col_writer.add_data4f(1., 1., 0., 1.)
            edge_prim.add_vertices(count, count + 1, count + 2, count + 3)
        else:
            pos_writer.add_data3f(pos)
            pos_writer.add_data3f(pos)
            col_writer.add_data4f(1., 1., 0., 1.)
            col_writer.add_data4f(1., 1., 0., 1.)
            edge_prim.add_vertices(count, count + 1)

    def remove_new_poly_vertex(self):

        tmp_data = self._tmp_data

        last_index = len(tmp_data["vert_pos"]) - 1

        if not last_index:
            return False

        if last_index > 1:
            del tmp_data["normals"][-1]

        del tmp_data["vert_pos"][-1]

        if last_index in tmp_data["vert_geom_rows"]:
            geom = tmp_data["geoms"]["vert"].node().modify_geom(0)
            vertex_data = geom.modify_vertex_data()
            row_count = vertex_data.get_num_rows() - 1
            vertex_data.set_num_rows(row_count)
            geom.modify_primitive(0).modify_vertices().set_num_rows(row_count)
            tmp_data["vert_geom_rows"].remove(last_index)

        if last_index in tmp_data["owned_verts"]:
            del tmp_data["owned_verts"][last_index]

        geom = tmp_data["geoms"]["poly"].node().modify_geom(0)

        if tmp_data["flip_normal"]:
            geom.reverse_in_place()

        geom.modify_vertex_data().set_num_rows(last_index + 1)
        tris_prim = geom.modify_primitive(0)

        if last_index > 1:
            del tmp_data["vert_indices"][-1]
            array = tris_prim.modify_vertices()
            array.set_num_rows(array.get_num_rows() - 3)
        else:
            tris_prim.modify_vertices().set_num_rows(0)

        if tmp_data["flip_normal"]:
            geom.reverse_in_place()

        if tmp_data["shared_verts"]:
            tmp_data["start_index"], tmp_data[
                "start_index_prev"] = tmp_data["shared_verts"][-1]
            del tmp_data["shared_verts"][-1]

        edge_geom = tmp_data["geoms"]["edge"].node().modify_geom(0)
        vertex_data = edge_geom.modify_vertex_data()
        count = vertex_data.get_num_rows() - 4
        vertex_data.set_num_rows(count)
        edge_geom.modify_primitive(0).modify_vertices().set_num_rows(count)

        return True

    def switch_new_poly_start_vertex(self):

        # When <Shift> is pressed, switch between the two vertices shared by the
        # last created triangle and the temporary triangle to determine which one
        # will be used as the new starting vertex. This effectively allows the user
        # to control the triangulation (to some degree) of the new polygon while
        # creating it.

        tmp_data = self._tmp_data

        last_index = len(tmp_data["vert_pos"]) - 1

        if not last_index:
            return

        if tmp_data["start_index"] == last_index:
            tmp_data["start_index"], tmp_data["start_index_prev"] = \
                tmp_data["start_index_prev"], tmp_data["start_index"]
        else:
            tmp_data["start_index_prev"] = tmp_data["start_index"]
            tmp_data["start_index"] = last_index

        edge_geom = tmp_data["geoms"]["edge"].node().modify_geom(0)
        vertex_data = edge_geom.modify_vertex_data()
        count = vertex_data.get_num_rows()
        col_writer = GeomVertexRewriter(vertex_data, "color")
        col_writer.set_row(count - 4)

        if col_writer.get_data4f() == VBase4(1., 1., 0., 1.):
            col_writer.set_data4f(.5, .5, .5, 1.)
            col_writer.set_data4f(.5, .5, .5, 1.)
            col_writer.set_data4f(1., 1., 0., 1.)
            col_writer.set_data4f(1., 1., 0., 1.)
        else:
            col_writer.set_data4f(1., 1., 0., 1.)
            col_writer.set_data4f(1., 1., 0., 1.)
            col_writer.set_data4f(.5, .5, .5, 1.)
            col_writer.set_data4f(.5, .5, .5, 1.)

    def flip_new_poly_normal(self):

        # When <Ctrl> is pressed, flip the normal of the new polygon.

        tmp_data = self._tmp_data

        if len(tmp_data["vert_pos"]) < 2:
            return

        tmp_data["flip_normal"] = not tmp_data["flip_normal"]

        poly_geom = tmp_data["geoms"]["poly"].node().modify_geom(0)
        vertex_data = poly_geom.modify_vertex_data()
        vertex_data = vertex_data.reverse_normals()
        poly_geom.set_vertex_data(vertex_data)
        poly_geom.reverse_in_place()

    def update_new_polygon(self, point):

        tmp_data = self._tmp_data

        grid_origin = Mgr.get(("grid", "origin"))
        pos = self._origin.get_relative_point(grid_origin, point)

        last_index = len(tmp_data["vert_pos"]) - 1

        if last_index > 0:

            geom = tmp_data["geoms"]["poly"].node().modify_geom(0)
            vertex_data = geom.modify_vertex_data()
            pos_writer = GeomVertexWriter(vertex_data, "vertex")
            pos_writer.set_row(last_index + 1)
            pos_writer.set_data3f(pos)

            if last_index == 1:

                indices = tmp_data["vert_indices"][-1]
                points = [tmp_data["vert_pos"][i] for i in indices[:2]]
                points.append(pos)
                plane = Plane(*points)
                normal = plane.get_normal()
                normal.normalize()

                if tmp_data["flip_normal"]:
                    normal *= -1.

                normal_writer = GeomVertexWriter(vertex_data, "normal")

                for row_index in indices:
                    normal_writer.set_row(row_index)
                    normal_writer.set_data3f(normal)

        geom = tmp_data["geoms"]["edge"].node().modify_geom(0)
        vertex_data = geom.modify_vertex_data()
        count = vertex_data.get_num_rows()
        pos_writer = GeomVertexWriter(vertex_data, "vertex")
        pos_writer.set_row(count - 1)
        pos_writer.set_data3f(pos)

        if last_index > 0:
            pos_writer.set_row(count - 3)
            pos_writer.set_data3f(pos)

    def finalize_poly_creation(self, cancel=False):

        tmp_data = self._tmp_data

        positions = tmp_data["vert_pos"]

        if not cancel and len(positions) < 3:
            return False

        # Clean up the temporary geometry

        tmp_geoms = tmp_data["geoms"]

        for subobj_type in ("vert", "edge", "poly"):
            tmp_geoms[subobj_type].remove_node()

        del self._tmp_data

        if cancel:
            return True

        # Create the new polygon

        subobjs = self._subobjs
        verts = subobjs["vert"]
        edges = subobjs["edge"]
        polys = subobjs["poly"]
        ordered_polys = self._ordered_polys
        merged_verts = self._merged_verts
        merged_verts_by_pos = {}
        merged_edges = self._merged_edges
        merged_edges_tmp = {}
        sel_vert_ids = self._selected_subobj_ids["vert"]
        sel_edge_ids = self._selected_subobj_ids["edge"]
        self._selected_subobj_ids["edge"] = []
        subobjs_to_select = {"vert": [], "edge": []}
        subobj_change = self._subobj_change

        owned_verts = tmp_data["owned_verts"]
        indices = tmp_data["vert_indices"]
        del indices[-1]
        normal = tmp_data["normals"][-1]
        normal.normalize()

        if tmp_data["flip_normal"]:
            normal *= -1.

        row_index = 0
        verts_by_pos = {}
        poly_verts = []
        edge_data = []
        triangles = []

        for tri_data in indices:

            if tmp_data["flip_normal"]:
                tri_data = tri_data[::-1]

            tri_vert_ids = []

            for pos_index in tri_data:

                if pos_index in verts_by_pos:

                    vertex = verts_by_pos[pos_index]
                    vert_id = vertex.get_id()

                else:

                    pos = positions[pos_index]
                    vertex = Mgr.do("create_vert", self, pos)
                    vertex.set_row_index(row_index)
                    row_index += 1
                    vertex.set_normal(normal)
                    vert_id = vertex.get_id()
                    verts[vert_id] = vertex
                    verts_by_pos[pos_index] = vertex
                    poly_verts.append(vertex)

                    if pos_index in owned_verts:
                        merged_vert = owned_verts[pos_index]
                        if merged_vert.get_id() in sel_vert_ids:
                            subobjs_to_select["vert"].append(vertex)
                    elif pos_index in merged_verts_by_pos:
                        merged_vert = merged_verts_by_pos[pos_index]
                    else:
                        merged_vert = Mgr.do("create_merged_vert", self)
                        merged_verts_by_pos[pos_index] = merged_vert

                    merged_vert.append(vert_id)
                    merged_verts[vert_id] = merged_vert

                tri_vert_ids.append(vert_id)

            for i, j in ((0, 1), (1, 2), (0, 2)):

                edge_verts = sorted(
                    [verts[tri_vert_ids[i]], verts[tri_vert_ids[j]]])

                if edge_verts in edge_data:
                    edge_data.remove(edge_verts)
                else:
                    edge_data.append(edge_verts)

            triangles.append(tuple(tri_vert_ids))

        owned_verts = owned_verts.values()

        for merged_vert in owned_verts:
            for vert_id in merged_vert:
                for edge_id in verts[vert_id].get_edge_ids():
                    mvs = [merged_verts[v_id] for v_id in edges[edge_id]]
                    if mvs[0] not in owned_verts or mvs[1] not in owned_verts:
                        continue
                    merged_edge_verts = tuple(sorted(mvs))
                    merged_edge = merged_edges[edge_id]
                    merged_edges_tmp[merged_edge_verts] = merged_edge

        poly_edges = []

        for edge_verts in edge_data:

            edge = Mgr.do("create_edge", self, edge_verts)
            edge_id = edge.get_id()
            edges[edge_id] = edge
            poly_edges.append(edge)
            vert_ids = [vert.get_id() for vert in edge_verts]
            merged_edge_verts = tuple(
                sorted([merged_verts[v_id] for v_id in vert_ids]))

            if merged_edge_verts in merged_edges_tmp:
                merged_edge = merged_edges_tmp[merged_edge_verts]
                if merged_edge[0] in sel_edge_ids:
                    subobjs_to_select["edge"].append(edge)
            else:
                merged_edge = Mgr.do("create_merged_edge", self)

            merged_edge.append(edge_id)
            merged_edges[edge_id] = merged_edge

        polygon = Mgr.do("create_poly", self, triangles,
                         poly_edges, poly_verts)
        ordered_polys.append(polygon)
        poly_id = polygon.get_id()
        polys[poly_id] = polygon
        subobj_change["vert"]["created"] = poly_verts
        subobj_change["edge"]["created"] = poly_edges
        subobj_change["poly"]["created"] = [polygon]

        # Update geometry structures

        vert_count = polygon.get_vertex_count()
        old_count = self._data_row_count
        count = old_count + vert_count
        self._data_row_count = count

        geoms = self._geoms
        geom_node_top = geoms["top"]["shaded"].node()
        vertex_data_top = geom_node_top.modify_geom(0).modify_vertex_data()
        vertex_data_top.reserve_num_rows(count)

        pos_writer = GeomVertexWriter(vertex_data_top, "vertex")
        pos_writer.set_row(old_count)
        col_writer = GeomVertexWriter(vertex_data_top, "color")
        col_writer.set_row(old_count)
        normal_writer = GeomVertexWriter(vertex_data_top, "normal")
        normal_writer.set_row(old_count)

        pickable_type_id = PickableTypes.get_id("poly")
        picking_col_id = polygon.get_picking_color_id()
        picking_color = get_color_vec(picking_col_id, pickable_type_id)

        for vert in poly_verts:
            vert.offset_row_index(old_count)
            pos = vert.get_pos()
            pos_writer.add_data3f(pos)
            col_writer.add_data4f(picking_color)
            normal_writer.add_data3f(normal)

        vertex_data_vert = self._vertex_data["vert"]
        vertex_data_tmp = GeomVertexData(vertex_data_vert)
        col_writer = GeomVertexWriter(vertex_data_tmp, "color")
        col_writer.set_row(old_count)

        pickable_type_id = PickableTypes.get_id("vert")

        for vert in poly_verts:
            picking_color = get_color_vec(
                vert.get_picking_color_id(), pickable_type_id)
            col_writer.add_data4f(picking_color)

        vertex_data_vert.set_num_rows(count)
        vertex_data_vert.set_array(
            1, GeomVertexArrayData(vertex_data_tmp.get_array(1)))

        sel_state = self._subobj_sel_state
        sel_state["vert"]["unselected"].extend(range(old_count, count))
        sel_state["poly"]["unselected"].extend(polygon[:])
        sel_state["edge"]["unselected"] = edge_state_unsel = []
        sel_state["edge"]["selected"] = []

        start_row_indices = []
        end_row_indices = []
        picking_colors1 = {}
        picking_colors2 = {}
        pickable_type_id = PickableTypes.get_id("edge")

        for edge in poly_edges:

            row1, row2 = [verts[v_id].get_row_index() for v_id in edge]

            if row1 in start_row_indices or row2 in end_row_indices:
                row1, row2 = row2, row1
                edge.switch_vertex_order()

            start_row_indices.append(row1)
            end_row_indices.append(row2)

            picking_color = get_color_vec(
                edge.get_picking_color_id(), pickable_type_id)
            picking_colors1[row1] = picking_color
            picking_colors2[row2 + count] = picking_color

        vertex_data_edge = self._vertex_data["edge"]
        vertex_data_tmp = GeomVertexData(vertex_data_edge)
        vertex_data_tmp.set_num_rows(count)
        col_writer = GeomVertexWriter(vertex_data_tmp, "color")
        col_writer.set_row(old_count)

        for row_index in sorted(picking_colors1.iterkeys()):
            picking_color = picking_colors1[row_index]
            col_writer.add_data4f(picking_color)

        data = vertex_data_tmp.get_array(1).get_handle().get_data()

        vertex_data_tmp = GeomVertexData(vertex_data_edge)
        array = vertex_data_tmp.modify_array(1)
        stride = array.get_array_format().get_stride()
        array.modify_handle().set_subdata(0, old_count * stride, "")
        vertex_data_tmp.set_num_rows(count)
        col_writer = GeomVertexWriter(vertex_data_tmp, "color")
        col_writer.set_row(old_count)

        for row_index in sorted(picking_colors2.iterkeys()):
            picking_color = picking_colors2[row_index]
            col_writer.add_data4f(picking_color)

        data += vertex_data_tmp.get_array(1).get_handle().get_data()

        vertex_data_edge.set_num_rows(count * 2)
        vertex_data_edge.modify_array(1).modify_handle().set_data(data)

        lines_prim = GeomLines(Geom.UH_static)
        lines_prim.reserve_num_vertices(count * 2)

        for poly in ordered_polys:
            for edge in poly.get_edges():
                row1, row2 = [verts[v_id].get_row_index() for v_id in edge]
                lines_prim.add_vertices(row1, row2 + count)
                edge_state_unsel.append(row1)
                if edge.get_id() in sel_edge_ids:
                    subobjs_to_select["edge"].append(edge)

        geom_node = geoms["top"]["wire"].node()
        geom_node.modify_geom(0).set_primitive(0, lines_prim)
        geom_node = geoms["edge"]["unselected"].node()
        geom_node.modify_geom(0).set_primitive(0, GeomLines(lines_prim))
        geom_node = geoms["edge"]["selected"].node()
        geom_node.modify_geom(0).modify_primitive(
            0).modify_vertices().modify_handle().set_data("")

        vertex_data_poly = self._vertex_data["poly"]
        vertex_data_poly.set_num_rows(count)

        vertex_data_top = geom_node_top.get_geom(0).get_vertex_data()
        pos_array = vertex_data_top.get_array(0)
        pos_data = pos_array.get_handle().get_data()
        poly_array = vertex_data_top.get_array(1)
        vertex_data_vert.set_array(0, GeomVertexArrayData(pos_array))
        vertex_data_poly.set_array(0, GeomVertexArrayData(pos_array))
        vertex_data_poly.set_array(1, GeomVertexArrayData(poly_array))
        array = GeomVertexArrayData(pos_array)
        array.modify_handle().set_data(pos_data * 2)
        vertex_data_edge.set_array(0, array)

        tris_prim = geom_node_top.modify_geom(0).modify_primitive(0)
        start = tris_prim.get_num_vertices()

        for vert_ids in triangles:
            tris_prim.add_vertices(
                *[verts[v_id].get_row_index() for v_id in vert_ids])

        array = tris_prim.get_vertices()
        stride = array.get_array_format().get_stride()
        start *= stride
        size = len(polygon) * stride
        data = array.get_handle().get_subdata(start, size)
        geom_node = geoms["poly"]["unselected"].node()
        prim = geom_node.modify_geom(0).modify_primitive(0)
        handle = prim.modify_vertices().modify_handle()
        handle.set_data(handle.get_data() + data)

        tmp_prim = GeomPoints(Geom.UH_static)
        tmp_prim.reserve_num_vertices(vert_count)
        tmp_prim.add_next_vertices(vert_count)
        tmp_prim.offset_vertices(old_count)
        array = tmp_prim.get_vertices()
        data = array.get_handle().get_data()
        geom_node = geoms["vert"]["unselected"].node()
        prim = geom_node.modify_geom(0).modify_primitive(0)
        handle = prim.modify_vertices().modify_handle()
        handle.set_data(handle.get_data() + data)

        # Miscellaneous updates

        polygon.update_center_pos()
        polygon.update_normal()

        merged_subobjs = {"vert": merged_verts, "edge": merged_edges}

        for subobj_type in ("vert", "edge"):
            if subobjs_to_select[subobj_type]:
                subobj = subobjs_to_select[subobj_type][0]
                subobj_id = subobj.get_id()
                merged_subobj = merged_subobjs[subobj_type][subobj_id]
                # since set_selected(...) processes *all* subobjects referenced by the
                # merged subobject, it is replaced by a temporary merged subobject that
                # only references the newly created subobjects;
                # as an optimization, one temporary merged subobject references all
                # newly created subobjects, so self.set_selected() needs to be called
                # only once
                tmp_merged_subobj = Mgr.do(
                    "create_merged_%s" % subobj_type, self)
                for s in subobjs_to_select[subobj_type]:
                    tmp_merged_subobj.append(s.get_id())
                merged_subobjs[subobj_type][subobj_id] = tmp_merged_subobj
                self.set_selected(subobj, True, False)
                # the original merged subobject can now be restored
                merged_subobjs[subobj_type][subobj_id] = merged_subobj
                subobj_change.setdefault("selection", []).append(subobj_type)
                self._update_verts_to_transform(subobj_type)

        self._update_verts_to_transform("poly")
        self._origin.node().set_bounds(geom_node_top.get_bounds())
        self.get_toplevel_object().get_bbox().update(*self._origin.get_tight_bounds())

        return True

    def end_poly_creation(self):

        # Make the polygons pickable again at polygon level instead of the
        # vertices

        picking_mask = Mgr.get("picking_mask")
        geom_roots = self._geom_roots
        geom_roots["poly"].show_through(picking_mask)
        geom_roots["vert"].show(picking_mask)


class PolygonCreationManager(BaseObject):

    def __init__(self):

        self._vert_positions = []
        self._pixel_under_mouse = VBase4()
        self._vert_is_under_mouse = False
        self._picked_verts = []
        self._geom_data_objs = []
        self._active_geom_data_obj = None
        self._interactive_creation_started = False
        self._interactive_creation_ended = False

    def setup(self):

        add_state = Mgr.add_state
        add_state("poly_creation_mode", -10,
                  self.__enter_creation_mode, self.__exit_creation_mode)
        add_state("poly_creation", -11)

        def cancel_creation():

            self.__finalize_poly_creation(cancel=True)

        bind = Mgr.bind_state
        bind("poly_creation_mode", "create poly -> navigate", "space",
             lambda: Mgr.enter_state("navigation_mode"))
        bind("poly_creation_mode", "create poly -> select", "escape",
             lambda: Mgr.exit_state("poly_creation_mode"))
        bind("poly_creation_mode", "exit poly creation mode", "mouse3-up",
             lambda: Mgr.exit_state("poly_creation_mode"))
        bind("poly_creation_mode", "start poly creation",
             "mouse1", self.__init_poly_creation)
        bind("poly_creation", "add poly vertex",
             "mouse1", self.__add_poly_vertex)
        bind("poly_creation", "remove poly vertex",
             "backspace", self.__remove_poly_vertex)
        bind("poly_creation", "switch poly start vertex",
             "shift", self.__switch_start_vertex)
        bind("poly_creation", "flip poly normal",
             "control", self.__flip_poly_normal)
        bind("poly_creation", "quit poly creation", "escape", cancel_creation)
        bind("poly_creation", "cancel poly creation",
             "mouse3-up", cancel_creation)

        status_data = Mgr.get_global("status_data")
        mode_text = "Create polygon"
        info_text = "LMB to create first vertex; RMB to cancel"
        status_data["create_poly"] = {"mode": mode_text, "info": info_text}
        info_text = "LMB to add vertex; <Backspace> to undo; " \
                    "click a previously added vertex to finalize; " \
                    "<Ctrl> to flip normal; <Shift> to turn diagonal; RMB to cancel"
        status_data["start_poly_creation"] = {
            "mode": mode_text, "info": info_text}

        return True

    def __enter_creation_mode(self, prev_state_id, is_active):

        if self._interactive_creation_ended:

            self._interactive_creation_ended = False

        else:

            editable_geoms = Mgr.get("selection", "top")
            geom_data_objs = [geom.get_geom_object().get_geom_data_object()
                              for geom in editable_geoms]

            for data_obj in geom_data_objs:
                data_obj.prepare_poly_creation()

            self._geom_data_objs = geom_data_objs

            Mgr.set_global("active_transform_type", "")
            Mgr.update_app("active_transform_type", "")
            Mgr.set_cursor("create")
            Mgr.add_task(self.__check_vertex_under_mouse,
                         "check_vertex_under_mouse", sort=3)

        Mgr.update_app("status", "create_poly")

    def __exit_creation_mode(self, next_state_id, is_active):

        if self._interactive_creation_started:

            self._interactive_creation_started = False

        else:

            Mgr.set_cursor("main")

            for data_obj in self._geom_data_objs:
                data_obj.end_poly_creation()

            self._geom_data_objs = []

            Mgr.remove_task("check_vertex_under_mouse")

    def __check_vertex_under_mouse(self, task):

        # Check if there is an existing vertex at the mouse position and set the
        # mouse cursor accordingly.

        self._pixel_under_mouse = Mgr.get("pixel_under_mouse")
        vert_is_under_mouse = self._pixel_under_mouse != VBase4()

        if vert_is_under_mouse != self._vert_is_under_mouse:

            self._vert_is_under_mouse = vert_is_under_mouse

            if vert_is_under_mouse:
                Mgr.set_cursor("select")
            else:
                Mgr.set_cursor("create")

        return task.cont

    def __get_point_on_grid(self):

        if not self.mouse_watcher.has_mouse():
            return

        mouse_pos = self.mouse_watcher.get_mouse()

        return Mgr.get(("grid", "point_at_screen_pos"), mouse_pos)

    def __get_vertex(self):

        r, g, b, a = [int(round(c * 255.)) for c in self._pixel_under_mouse]
        color_id = r << 16 | g << 8 | b  # credit to coppertop @ panda3d.org

        return Mgr.get("vert", color_id)

    def __init_poly_creation(self):

        if self._vert_is_under_mouse:

            vertex = self.__get_vertex()

            if not vertex:
                return

            vertex = vertex.get_merged_vertex()
            point = None
            geom_data_obj = vertex.get_geom_data_object()

        else:

            point = self.__get_point_on_grid()

            if not point:
                return

            vertex = None
            geom_data_obj = self._geom_data_objs[0]

        geom_data_obj.init_poly_creation()
        geom_data_obj.add_new_poly_vertex(vertex, point)

        self._picked_verts.append(vertex)
        self._active_geom_data_obj = geom_data_obj

        self._interactive_creation_started = True
        self._interactive_creation_ended = False

        Mgr.update_app("status", "start_poly_creation")
        Mgr.enter_state("poly_creation")
        Mgr.add_task(self.__update_polygon, "update_polygon", sort=4)

    def __update_polygon(self, task):

        if self._vert_is_under_mouse:

            vertex = self.__get_vertex()

            if not vertex:
                return task.cont

            grid_origin = Mgr.get(("grid", "origin"))
            point = vertex.get_pos(grid_origin)

        else:

            point = self.__get_point_on_grid()

            if not point:
                return task.cont

        self._active_geom_data_obj.update_new_polygon(point)

        return task.cont

    def __add_poly_vertex(self):

        if self._vert_is_under_mouse:

            vertex = self.__get_vertex()

            if not vertex:
                # one of the previously added new vertices is picked, so the polygon
                # will be finalized
                self.__finalize_poly_creation()
                return

            vertex = vertex.get_merged_vertex()

            if vertex in self._picked_verts:
                # one of the previously picked existing vertices is picked again, so the
                # polygon will be finalized
                self.__finalize_poly_creation()
                return

            point = None

        else:

            point = self.__get_point_on_grid()

            if not point:
                return

            vertex = None

        self._picked_verts.append(vertex)
        self._active_geom_data_obj.add_new_poly_vertex(vertex, point)

    def __remove_poly_vertex(self):

        del self._picked_verts[-1]

        if self._picked_verts:
            self._active_geom_data_obj.remove_new_poly_vertex()
        else:
            self.__finalize_poly_creation(cancel=True)

    def __switch_start_vertex(self):

        self._active_geom_data_obj.switch_new_poly_start_vertex()

    def __flip_poly_normal(self):

        self._active_geom_data_obj.flip_new_poly_normal()

    def __finalize_poly_creation(self, cancel=False):

        geom_data_obj = self._active_geom_data_obj

        if not geom_data_obj.finalize_poly_creation(cancel=cancel):
            return

        self._active_geom_data_obj = None
        self._picked_verts = []
        self._interactive_creation_started = False
        self._interactive_creation_ended = True

        Mgr.remove_task("update_polygon")
        Mgr.enter_state("poly_creation_mode")

        if cancel:
            return

        Mgr.do("update_history_time")
        obj_id = geom_data_obj.get_toplevel_object().get_id()
        obj_data = {obj_id: geom_data_obj.get_data_to_store("subobj_change")}
        event_descr = "Create polygon"
        event_data = {"objects": obj_data}
        Mgr.do("add_history", event_descr, event_data, update_time_id=False)


MainObjects.add_class(PolygonCreationManager)