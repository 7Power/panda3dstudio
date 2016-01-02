from ..base import *


class Grid(BaseObject):

    def __init__(self):

        BaseObject.__init__(self)

        self._origin = self.world.attach_new_node("grid")
        self._grid_lines = self._origin.attach_new_node("grid_lines")
        self._axes = self._grid_lines.attach_new_node("grid_axis_lines")
        self._axis_lines = {}
        self._grid_planes = {}
        self._planes = {}
        self._plane_hprs = {"XY": (0., 0., 0.), "XZ": (
            0., 90., 0.), "YZ": (0., 0., 90.)}
        self._horizon_origin = None
        self._horizon_line = None
        self._axis_indicator = None
        self._projector_origin = None
        self._projector = None
        self._projector_lens = None

        self.expose("origin", lambda: self._origin)
        self.expose("hpr", self._origin.get_hpr)
        self.expose("point_at_screen_pos", self.__get_point_at_screen_pos)
        Mgr.expose("grid", lambda: self)
        Mgr.accept("update_grid", self.__update)
        Mgr.add_app_updater("active_grid_plane", self.__set_plane)

        angle = self.cam_lens.get_fov()[1] * .5
        self._ref_dist = .25 * 300. / math.tan(math.radians(angle))

        self._scale = 1.
        self._spacing = 10.

        Mgr.set_global("active_grid_plane", "XY")

        self._active_plane_id = "YZ"

    def setup(self):

        picking_mask = Mgr.get("picking_mask")

        if picking_mask is None:
            return False

        self._origin.hide(picking_mask)

        for plane_id in ("XY", "XZ", "YZ"):
            plane = self.__create_plane(plane_id)
            plane.reparent_to(self._grid_lines)
            plane.hide()
            self._grid_planes[plane_id] = plane

        self.__create_horizon()
        self.__create_axis_indicator()

        for i, axis_id in enumerate("XYZ"):
            axis_line = self.__create_line(axis_id)
            axis_line.reparent_to(self._axes)
            color = VBase3()
            color[i] = 1.
            axis_line.set_color(*color)
            self._axis_lines[axis_id] = axis_line

        # to make the axis lines show on top of any grid lines without causing
        # z-fighting, they can be put (together with the grid planes) into a
        # fixed bin - that is drawn *after* objects in the default bin - with
        # a lower draw_order than the grid planes, so they are drawn after
        # those also
        self._axes.set_bin("fixed", 2)
        # no need to write the axis lines to the depth buffer - they will be drawn
        # last anyway - as long as depth *testing* is NOT disabled for them, so the
        # depth of previously drawn geometry will be taken into consideration
        # (except for the depth of the grid planes, as these should not be written
        # to the depth buffer either, eliminating the z-fighting problem)
        self._axes.set_depth_write(False)

        # also add the grid planes to the fixed cull bin, but with a higher draw_order
        # than the axis lines, so the latter are drawn afterwards;
        # do NOT write the grid planes to the depth buffer, so their depth is not
        # taken into account when drawing the axis lines (which will therefore be
        # drawn completely on top of the grid planes without any z-fighting);
        # as with the axis lines, depth testing *must* be enabled for them so they
        # are drawn correctly with respect to previously drawn geometry
        for plane in self._grid_planes.itervalues():
            plane.set_bin("fixed", 1)
            plane.set_depth_write(False)

        self._origin.set_transparency(TransparencyAttrib.M_alpha)
        tex_stage = TextureStage.get_default()
        lens = PerspectiveLens()
        lens.set_fov(145., 145.)
        lens_node = LensNode("grid_proj_lens", lens)
        self._projector_origin = self._origin.attach_new_node(
            "grid_proj_origin")
        self._projector = self._projector_origin.attach_new_node(
            "grid_projector")
        self._projector_lens = self._projector.attach_new_node(lens_node)
        self._projector_lens.set_p(-90.)
        self._grid_lines.set_tex_gen(tex_stage, TexGenAttrib.M_world_position)
        self._grid_lines.set_tex_projector(
            tex_stage, self.world, self._projector_lens)
        tex = Mgr.load_tex(GFX_PATH + "gridfade.png")
        tex.set_wrap_u(Texture.WM_clamp)
        tex.set_wrap_v(Texture.WM_clamp)
        self._grid_lines.set_texture(tex_stage, tex)

        for i, axis_id in enumerate("XYZ"):
            plane_id = "XYZ".replace(axis_id, "")
            normal = Vec3(0., 0., 0.)
            normal[i] = 1.
            plane_node = PlaneNode("grid_plane_%s" %
                                   plane_id.lower(), Plane(normal, Point3()))
            self._planes[plane_id] = self._origin.attach_new_node(plane_node)

        self.__set_plane("XY")

        return True

    def __create_horizon(self):

        vertex_format = GeomVertexFormat.get_v3n3cpt2()
        vertex_data = GeomVertexData(
            "horizon_data", vertex_format, Geom.UH_static)
        horizon_geom = Geom(vertex_data)

        pos_writer = GeomVertexWriter(vertex_data, "vertex")
        col_writer = GeomVertexWriter(vertex_data, "color")

        pos_writer.add_data3f(-1000., 100., 0.)
        pos_writer.add_data3f(1000., 100., 0.)

        col_writer.add_data4f(.35, .35, .35, 1.0)
        col_writer.add_data4f(.35, .35, .35, 1.0)

        horizon_line = GeomLines(Geom.UH_static)
        horizon_line.add_vertices(0, 1)
        horizon_geom.add_primitive(horizon_line)
        horizon_node = GeomNode("horizon")
        horizon_node.add_geom(horizon_geom)
        self._horizon_origin = self._origin.attach_new_node("horizon_origin")
        self._horizon_line = self._horizon_origin.attach_new_node(horizon_node)
        self._horizon_line.set_bin("background", 0)
        self._horizon_line.set_depth_test(False)
        self._horizon_line.set_depth_write(False)

    def __create_axis_indicator(self):

        vertex_format = GeomVertexFormat.get_v3n3cpt2()
        vertex_data = GeomVertexData(
            "axis_indicator_data", vertex_format, Geom.UH_static)
        axis_indicator_geom = Geom(vertex_data)

        pos_writer = GeomVertexWriter(vertex_data, "vertex")
        col_writer = GeomVertexWriter(vertex_data, "color")

        for i in range(3):

            pos = VBase3()
            pos[i] = 5.

            color = VBase4(0., 0., 0., 1.0)
            color[i] = .35

            pos_writer.add_data3f(0., 0., 0.)
            pos_writer.add_data3f(pos)

            col_writer.add_data4f(color)
            col_writer.add_data4f(color)

            axis_indicator_line = GeomLines(Geom.UH_static)
            axis_indicator_line.add_vertices(i * 2, i * 2 + 1)
            axis_indicator_geom.add_primitive(axis_indicator_line)

        axis_indicator_node = GeomNode("axis_indicator")
        axis_indicator_node.add_geom(axis_indicator_geom)
        self._axis_indicator = self._origin.attach_new_node(
            axis_indicator_node)
        self._axis_indicator.set_bin("background", 0)
        self._axis_indicator.set_depth_test(False)
        self._axis_indicator.set_depth_write(False)

    def __create_line(self, axis_id):

        coord_index = "XYZ".index(axis_id)
        pos1 = VBase3()
        pos1[coord_index] = -1000.
        pos2 = VBase3()
        pos2[coord_index] = 1000.

        vertex_format = GeomVertexFormat.get_v3n3cpt2()
        vertex_data = GeomVertexData(
            "gridline_data", vertex_format, Geom.UH_static)

        pos_writer = GeomVertexWriter(vertex_data, "vertex")
        pos_writer.add_data3f(pos1)
        pos_writer.add_data3f(pos2)

        line = GeomLines(Geom.UH_static)
        line.add_vertices(0, 1)
        line_geom = Geom(vertex_data)
        line_geom.add_primitive(line)
        line_node = GeomNode("grid_line_%s" % axis_id.lower())
        line_node.add_geom(line_geom)

        return NodePath(line_node)

    def __create_plane(self, plane_id):

        node_path = NodePath("grid_plane_%s" % plane_id.lower())

        axis_id1, axis_id2 = plane_id

        color1 = VBase4(0., 0., 0., 1.0)
        color_index1 = "XYZ".index(axis_id1)
        color1[color_index1] = .3
        color2 = VBase4(0., 0., 0., 1.0)
        color_index2 = "XYZ".index(axis_id2)
        color2[color_index2] = .3

        def create_lines(axis_id, color):

            grid_half_np = node_path.attach_new_node("")

            grey_lines = grid_half_np.attach_new_node("")
            grey_lines.set_color(.35, .35, .35, 1.)

            colored_lines = grid_half_np.attach_new_node("")
            colored_lines.set_color(color)

            line = self.__create_line(axis_id)

            coord_index = "XYZ".index(
                axis_id1 if axis_id == axis_id2 else axis_id2)

            for i in range(1, 101):

                if i % 5 == 0:
                    line_copy = line.copy_to(colored_lines)
                else:
                    line_copy = line.copy_to(grey_lines)

                pos = VBase3()
                pos[coord_index] = i * 10.
                line_copy.set_pos(pos)

            mirrored_half = grid_half_np.copy_to(node_path)
            scale = VBase3(1., 1., 1.)
            scale_index = "XYZ".index(
                axis_id1 if axis_id == axis_id2 else axis_id2)
            scale[scale_index] = -1.
            mirrored_half.set_scale(scale)

        create_lines(axis_id1, color1)
        create_lines(axis_id2, color2)

        central_line1 = self.__create_line(axis_id1)
        central_line1.reparent_to(node_path)
        central_line1.set_color(color1)
        central_line2 = self.__create_line(axis_id2)
        central_line2.reparent_to(node_path)
        central_line2.set_color(color2)

        node_path.flatten_strong()

        return node_path

    def __update(self, force=False):

        cam_pos = self.cam.get_pos(self._origin)

        axis_id1, axis_id2 = self._active_plane_id
        axis_id3 = "XYZ".replace(axis_id1, "").replace(axis_id2, "")
        a_index = "XYZ".index(axis_id1)
        b_index = "XYZ".index(axis_id2)
        c_index = "XYZ".index(axis_id3)
        a = cam_pos[a_index]
        b = cam_pos[b_index]
        c = cam_pos[c_index] * (-1. if c_index == 1 else 1.)

        c_offset = min(1000000., abs(c))
        d = c_offset / self._ref_dist

        if d > .001:
            ceil1 = 10. ** math.ceil(math.log(d, 10.))
            ceil2 = ceil1 * .5
            scale = ceil2 if ceil2 > d else ceil1
        else:
            scale = .001

        if force or scale != self._scale:
            self._grid_planes[self._active_plane_id].set_scale(scale)
            self._axis_lines[axis_id1].set_scale(scale)
            self._axis_lines[axis_id2].set_scale(scale)
            self._scale = scale
            spacing_str = str(self._spacing * scale)
            Mgr.update_app("gridspacing", spacing_str)

        size = 50. * self._scale
        a_offset = abs(a) // size * (-size if a < 0. else size)
        b_offset = abs(b) // size * (-size if b < 0. else size)
        offset = VBase3()
        offset[a_index] = a_offset
        offset[b_index] = b_offset
        self._grid_planes[self._active_plane_id].set_pos(offset)
        offset = VBase3()
        offset[a_index] = a_offset
        self._axis_lines[axis_id1].set_pos(offset)
        offset = VBase3()
        offset[b_index] = b_offset
        self._axis_lines[axis_id2].set_pos(offset)

        self._projector_origin.set_pos(cam_pos)
        self._projector.set_h(self.cam.get_h(self._projector_origin))
        self._horizon_origin.set_pos(cam_pos)
        self._horizon_line.set_h(self.cam.get_h(self._horizon_origin))

        proj = -5. * c / (5. + abs(c))
        pos = self._origin.get_relative_point(
            self._horizon_line, Point3(0., 100., proj))
        self._axis_indicator.set_pos(pos)

    def __set_plane(self, plane_id):

        if plane_id != self._active_plane_id:

            Mgr.set_global("active_grid_plane", plane_id)

            self._grid_planes[self._active_plane_id].hide()
            self._grid_planes[plane_id].show()

            self._active_plane_id = plane_id

            axis_id1, axis_id2 = plane_id
            axis_id3 = "XYZ".replace(axis_id1, "").replace(axis_id2, "")

            self._axis_lines[axis_id1].show()
            self._axis_lines[axis_id2].show()
            self._axis_lines[axis_id3].hide()

            self._horizon_origin.set_hpr(self._plane_hprs[plane_id])
            self._projector_origin.set_hpr(self._plane_hprs[plane_id])

        self.__update(force=True)

    def __get_point_at_screen_pos(self, screen_pos):

        near_point = Point3()
        far_point = Point3()
        self.cam_lens.extrude(screen_pos, near_point, far_point)

        point = Point3()
        plane = self._planes[self._active_plane_id].node().get_plane()

        if plane.intersects_line(point,
                                 self._origin.get_relative_point(
                                     self.cam, near_point),
                                 self._origin.get_relative_point(self.cam, far_point)):
            return point


MainObjects.add_class(Grid)
