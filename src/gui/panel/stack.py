from ..base import *
from ..menu import *
from ..dialog import *
from ..scroll import ScrollPaneFrame, ScrollPane
from .panel import Panel


class PanelStack(ScrollPane):

    def __init__(self, frame_parent):

        frame_gfx_data = {
            "": (
                ("panelstack_topleft", "panelstack_top", "panelstack_topright"),
                ("panelstack_left", "panelstack_center", "panelstack_right"),
                ("panelstack_bottomleft", "panelstack_bottom", "panelstack_bottomright")
            )
        }
        bar_gfx_data = {
            "": (
                ("panel_scrollbar_topleft", "panel_scrollbar_top", "panel_scrollbar_topright"),
                ("panel_scrollbar_left", "panel_scrollbar_center", "panel_scrollbar_right"),
                ("panel_scrollbar_bottomleft", "panel_scrollbar_bottom", "panel_scrollbar_bottomright")
            )
        }
        thumb_gfx_data = {
            "normal": (
                ("panel_scrollthumb_normal_topleft", "panel_scrollthumb_normal_top",
                 "panel_scrollthumb_normal_topright"),
                ("panel_scrollthumb_normal_left", "panel_scrollthumb_normal_center",
                 "panel_scrollthumb_normal_right"),
                ("panel_scrollthumb_normal_bottomleft", "panel_scrollthumb_normal_bottom",
                 "panel_scrollthumb_normal_bottomright")
            ),
            "hilited": (
                ("panel_scrollthumb_hilited_topleft", "panel_scrollthumb_hilited_top",
                 "panel_scrollthumb_hilited_topright"),
                ("panel_scrollthumb_hilited_left", "panel_scrollthumb_hilited_center",
                 "panel_scrollthumb_hilited_right"),
                ("panel_scrollthumb_hilited_bottomleft", "panel_scrollthumb_hilited_bottom",
                 "panel_scrollthumb_hilited_bottomright")
            )
        }
        append_scrollbar = not Skin["options"]["panel_scrollbar_left"]

        ScrollPane.__init__(self, frame_parent, "panel_stack", "vertical", "gui", frame_gfx_data,
                            bar_gfx_data, thumb_gfx_data, "panelstack_scrollbar",
                            append_scrollbar=append_scrollbar)

        self._panels = []
        self._panels_to_update = set()
        self._panels_to_resize = set()
        self._panels_to_hide = set()
        self._panels_to_show = set()
        self._panel_heights = []
        self._is_contents_locked = False
        self._clicked_panel = None

        self._menu = menu = Menu()
        item = menu.add("panels", "Panels", item_type="submenu")
        submenu = item.get_submenu()
        item = submenu.add("scroll_to_panel", "Scroll to", item_type="submenu")
        self._panel_menu = item.get_submenu()
        self._panel_menu_items = []
        submenu.add("sep0", item_type="separator")
        command = lambda: self._clicked_panel.expand(False)
        submenu.add("collapse_panel", "Collapse", command)

        def command():

            for panel in self._panels:
                if not panel.is_hidden() and panel is not self._clicked_panel:
                    panel.expand(False)

        submenu.add("collapse_other_panels", "Collapse others", command)

        def command():

            for panel in self._panels:
                if not panel.is_hidden() and panel is not self._clicked_panel:
                    panel.expand()

        submenu.add("expand_other_panels", "Expand others", command)

        def command():

            for panel in self._panels:
                if not panel.is_hidden():
                    panel.expand(False)

        submenu.add("collapse_all_panels", "Collapse all", command)
        item = menu.add("sections", "Sections", item_type="submenu")
        submenu = item.get_submenu()

        def command():

            for section in self._clicked_panel.get_sections():
                if not section.is_hidden():
                    section.expand(False)

        submenu.add("collapse_sections", "Collapse all", command)

        def command():

            for section in self._clicked_panel.get_sections():
                if not section.is_hidden():
                    section.expand()

        submenu.add("expand_sections", "Expand all", command)

    def _create_frame(self, parent, scroll_dir, cull_bin, gfx_data, bar_gfx_data,
                      thumb_gfx_data, bar_inner_border_id, has_mouse_region=True):

        return ScrollPaneFrame(parent, self, gfx_data, bar_gfx_data, thumb_gfx_data,
                               cull_bin, scroll_dir, bar_inner_border_id, has_mouse_region)

    def _get_mask_sort(self):

        return 100

    def _contents_needs_redraw(self):

        return not self._is_contents_locked

    def _copy_widget_images(self, pane_image): 

        for panel in self._panels:
            x_ref, y_ref = panel.get_pos(from_root=True)
            pane_image.copy_sub_image(panel.get_image(), x_ref, y_ref, 0, 0)

    def _can_scroll(self):

        if (self.get_mouse_watcher().get_over_region() is None
                or Dialog.get_dialogs() or Mgr.get("active_input_field")
                or Menu.is_menu_shown() or not Mgr.get("gui_enabled")):
            return False

        return True

    def __get_scroll_command(self, panel):

        def scroll_to_panel():

            offset = panel.get_pos(from_root=True)[1]
            self.get_scrollthumb().set_offset(offset)

        return scroll_to_panel

    def finalize(self):

        heights = self._panel_heights
        menu = self._panel_menu
        panel_menu_items = self._panel_menu_items
        command = lambda: None

        for panel in self._panels:
            panel.finalize()
            heights.append(panel.get_size()[1])
            command = self.__get_scroll_command(panel)
            item = menu.add("panel_{}".format(panel.get_id()), panel.get_name(), command)
            panel_menu_items.append(item)

        self._menu.update()

        self._sizer.lock_item_size()
        self._sizer.lock_mouse_regions()
        self._is_contents_locked = True

    def destroy(self):

        ScrollPane.destroy(self)

        self._clicked_panel = None
        self._menu.destroy()
        self._menu = None

    def show_menu(self, panel):

        self._clicked_panel = panel
        self._menu.show_at_mouse_pos()

    def set_pos(self, pos):

        WidgetCard.set_pos(self, pos)

        x, y = self.get_pos(from_root=True)
        self.get_widget_root_node().set_pos(x, 0, -y + self.get_scrollthumb().get_offset())

    def add_panel(self, panel):

        self._panels.append(panel)
        self._sizer.add(panel, expand=True)

    def get_panels(self):

        return self._panels

    def __offset_mouse_region_frames(self):

        exclude = "lr"

        for panel in self._panels_to_update:
            if not panel.is_hidden():
                panel.update_mouse_region_frames(exclude)

        self._panels_to_update = set()

    def __handle_panel_resize(self):

        heights = self._panel_heights
        new_heights = heights[:]
        sizer = self.get_sizer()
        h_virt_new = h_virt = sizer.get_virtual_size()[1]
        regions_to_copy = []
        prev_i = 0
        w = 0

        for i, panel in enumerate(self._panels):

            if panel in self._panels_to_hide | self._panels_to_show:
                continue

            if panel in self._panels_to_resize and not panel.is_hidden():

                w, h = panel.get_size()
                old_height = heights[i]
                new_height = h if panel.is_expanded() else Panel.collapsed_height
                new_heights[i] = new_height
                h_virt_new += new_height - old_height
                dh = sum(heights[prev_i:i])

                if dh:
                    y_dest = sum(new_heights[:prev_i])
                    y_src = sum(heights[:prev_i])
                    regions_to_copy.append((y_dest, y_src, dh))

                prev_i = i + 1

        if w == 0:
            self._panels_to_resize = set()
            return

        dh = sum(heights[prev_i:len(self._panels)])

        if dh:
            y_dest = sum(new_heights[:prev_i])
            y_src = sum(heights[:prev_i])
            regions_to_copy.append((y_dest, y_src, dh))

        self._panel_heights = new_heights

        img = self._image
        img_new = PNMImage(w, h_virt_new)

        for y_dest, y_src, dh in regions_to_copy:
            img_new.copy_sub_image(img, 0, y_dest, 0, y_src, w, dh)

        for panel in self._panels_to_resize:
            img_new.copy_sub_image(panel.get_image(), 0, panel.get_pos(from_root=True)[1], 0, 0)

        tex = self.get_texture()
        tex.load(img_new)
        self._image = img_new
        sizer.set_virtual_size((w, h_virt_new))

        tex_offset_y = self.get_quad().get_tex_offset(TextureStage.get_default())[1]

        width, height = self.get_size()
        tex_scale = (1., min(1., height / h_virt_new))
        x, y = self.get_pos(from_root=True)
        l = x
        r = x + width
        b = -(y + min(height, h_virt_new))
        t = -y
        quad = self.create_quad((l, r, b, t))
        quad.set_texture(tex)
        quad.set_y(-1.)
        quad.set_tex_scale(TextureStage.get_default(), *tex_scale)
        self.reset_sub_image_index()
        self._scrollthumb.update()
        self.update_mouse_region_frames()
        index = 0

        for i, panel in enumerate(self._panels):
            if panel in self._panels_to_resize:
                index = i
                break

        self._panels_to_update.update(self._panels[index + 1:])

        task = self.__offset_mouse_region_frames
        task_id = "offset_panel_mouse_region_frames"
        PendingTasks.add(task, task_id, batch_id="panel_mouse_region_update")

        self._panels_to_resize = set()

    def handle_panel_resize(self, panel):

        self._panels_to_resize.add(panel)
        task = self.__handle_panel_resize
        task_id = "handle_panel_resize"
        PendingTasks.add(task, task_id, batch_id="panel_change")

    def __toggle_panels(self):

        heights = self._panel_heights
        new_heights = heights[:]
        h_virt_new = h_virt = self._sizer.get_virtual_size()[1]
        regions_to_copy = []
        prev_i = 0

        for i, panel in enumerate(self._panels):

            if panel in self._panels_to_hide:

                old_height = heights[i]
                new_heights[i] = 0
                h_virt_new -= old_height
                dh = sum(heights[prev_i:i])

                if dh:
                    y_dest = sum(new_heights[:prev_i])
                    y_src = sum(heights[:prev_i])
                    regions_to_copy.append((y_dest, y_src, dh))

                prev_i = i + 1

            elif panel in self._panels_to_show:

                w, h = panel.get_size()
                new_height = h if panel.is_expanded() else Panel.collapsed_height
                new_heights[i] = new_height
                h_virt_new += new_height
                dh = sum(heights[prev_i:i])

                if dh:
                    y_dest = sum(new_heights[:prev_i])
                    y_src = sum(heights[:prev_i])
                    regions_to_copy.append((y_dest, y_src, dh))

                prev_i = i + 1

        dh = sum(heights[prev_i:len(self._panels)])

        if dh:
            y_dest = sum(new_heights[:prev_i])
            y_src = sum(heights[:prev_i])
            regions_to_copy.append((y_dest, y_src, dh))

        self._panel_heights = new_heights

        img = self._image
        w = img.get_x_size()
        img_new = PNMImage(w, h_virt_new)

        for y_dest, y_src, dh in regions_to_copy:
            img_new.copy_sub_image(img, 0, y_dest, 0, y_src, w, dh)

        for panel in self._panels_to_show:
            img_new.copy_sub_image(panel.get_image(), 0, panel.get_pos(from_root=True)[1], 0, 0)

        tex = self.get_texture()
        tex.load(img_new)
        self._image = img_new
        self._sizer.set_virtual_size((w, h_virt_new))

        tex_offset_y = self._quad.get_tex_offset(TextureStage.get_default())[1]
        self._quad.remove_node()

        width, height = self.get_size()
        tex_scale = (1., min(1., height / h_virt_new))
        x, y = self.get_pos(from_root=True)
        l = x
        r = x + width
        b = -(y + min(height, h_virt_new))
        t = -y
        cm = CardMaker("panel_stack_quad")
        cm.set_frame(l, r, b, t)
        self._quad = quad = Mgr.get("gui_root").attach_new_node(cm.generate())
        quad.set_texture(tex)
        quad.set_y(-1.)
        quad.set_tex_scale(TextureStage.get_default(), *tex_scale)
        self.reset_sub_image_index()
        self._scrollthumb.update()
        self.update_mouse_region_frames()
        index = 0

        for i, panel in enumerate(self._panels):
            if panel in self._panels_to_hide or panel in self._panels_to_show:
                index = i
                break

        self._panels_to_update.update(self._panels[index + 1:])

        task = self.__offset_mouse_region_frames
        task_id = "offset_panel_mouse_region_frames"
        PendingTasks.add(task, task_id, batch_id="panel_mouse_region_update")

        self._panels_to_hide = set()
        self._panels_to_show = set()
        self._panel_menu.update()

    def show_panel(self, panel, show=True):

        r = panel.show() if show else panel.hide()

        if not r:
            return

        panels = self._panels_to_show if show else self._panels_to_hide
        panels.add(panel)

        if show:
            index = self._panels.index(panel)
            menu_item = self._panel_menu_items[index]
            shown_panels = [p for p in self._panels if not p.is_hidden()]
            index = shown_panels.index(panel)
            self._panel_menu.add_item(menu_item, index)
        else:
            self._panel_menu.remove("panel_{}".format(panel.get_id()))

        task = self.__toggle_panels
        task_id = "toggle_panels"
        PendingTasks.add(task, task_id, batch_id="panel_change")
