"""Release Notes Editor — Write release notes with templates and translation."""
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gdk, Gio, GLib, Pango

import gettext
import locale
import os
import sys
import json
import datetime
import threading
import subprocess
import re

LOCALE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "po")
if not os.path.isdir(LOCALE_DIR):
    LOCALE_DIR = "/usr/share/locale"
locale.bindtextdomain("release-notes-editor", LOCALE_DIR)
gettext.bindtextdomain("release-notes-editor", LOCALE_DIR)
gettext.textdomain("release-notes-editor")
_ = gettext.gettext

APP_ID = "se.danielnylander.release.notes.editor"
SETTINGS_DIR = os.path.join(
    os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")),
    "release-notes-editor"
)
SETTINGS_FILE = os.path.join(SETTINGS_DIR, "settings.json")


def _load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE) as f:
            return json.load(f)
    return {"welcome_shown": False}


def _save_settings(s):
    os.makedirs(SETTINGS_DIR, exist_ok=True)
    with open(SETTINGS_FILE, "w") as f:
        json.dump(s, f, indent=2)



TEMPLATES = {
    "standard": """# {project} {version} Release Notes

## New Features

- Feature 1

## Bug Fixes

- Fix 1

## Known Issues

- Issue 1

## Upgrade Notes

- Note 1
""",
    "security": """# {project} {version} Security Advisory

## Summary

## Affected Versions

## Fix

## Credits

## Timeline
""",
}



class ReleaseNotesEditorWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title=_("Release Notes Editor"), default_width=1000, default_height=700)
        self.settings = _load_settings()
        
        self._current_file = None

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # Header
        headerbar = Adw.HeaderBar()
        title_widget = Adw.WindowTitle(title=_("Release Notes Editor"), subtitle="")
        headerbar.set_title_widget(title_widget)
        self._title_widget = title_widget

        
        new_btn = Gtk.Button(icon_name="document-new-symbolic", tooltip_text=_("New from template"))
        new_btn.connect("clicked", self._on_new)
        headerbar.pack_start(new_btn)
        
        open_btn = Gtk.Button(icon_name="document-open-symbolic", tooltip_text=_("Open"))
        open_btn.connect("clicked", self._on_open)
        headerbar.pack_start(open_btn)
        
        save_btn = Gtk.Button(icon_name="document-save-symbolic", tooltip_text=_("Save"))
        save_btn.connect("clicked", self._on_save)
        headerbar.pack_end(save_btn)

        # Menu
        menu = Gio.Menu()
        menu.append(_("Settings"), "app.settings")
        menu.append(_("Copy Debug Info"), "app.copy-debug")
        menu.append(_("Keyboard Shortcuts"), "app.shortcuts")
        menu.append(_("About Release Notes Editor"), "app.about")
        menu_btn = Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu)
        headerbar.pack_end(menu_btn)

        main_box.append(headerbar)

        
        # Editor paned: edit left, preview right
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_vexpand(True)
        
        # Left: editor
        left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        edit_label = Gtk.Label(label=_("Editor"), xalign=0)
        edit_label.add_css_class("heading")
        edit_label.set_margin_start(12)
        edit_label.set_margin_top(8)
        left_box.append(edit_label)
        
        edit_scroll = Gtk.ScrolledWindow(vexpand=True)
        self._editor = Gtk.TextView(monospace=True, wrap_mode=Gtk.WrapMode.WORD_CHAR)
        self._editor.set_top_margin(8)
        self._editor.set_left_margin(8)
        self._editor.set_right_margin(8)
        edit_scroll.set_child(self._editor)
        left_box.append(edit_scroll)
        paned.set_start_child(left_box)
        
        # Right: preview (simple)
        right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        preview_label = Gtk.Label(label=_("Preview"), xalign=0)
        preview_label.add_css_class("heading")
        preview_label.set_margin_start(12)
        preview_label.set_margin_top(8)
        right_box.append(preview_label)
        
        preview_scroll = Gtk.ScrolledWindow(vexpand=True)
        self._preview = Gtk.TextView(editable=False, wrap_mode=Gtk.WrapMode.WORD_CHAR)
        self._preview.set_top_margin(8)
        self._preview.set_left_margin(8)
        preview_scroll.set_child(self._preview)
        right_box.append(preview_scroll)
        paned.set_end_child(right_box)
        paned.set_position(500)
        
        main_box.append(paned)
        
        # Auto-update preview
        self._editor.get_buffer().connect("changed", self._on_text_changed)

        # Status bar
        self._status = Gtk.Label(label=_("Ready"), xalign=0)
        self._status.set_margin_start(12)
        self._status.set_margin_end(12)
        self._status.set_margin_top(4)
        self._status.set_margin_bottom(4)
        self._status.add_css_class("dim-label")
        main_box.append(self._status)

        self.set_content(main_box)

        if not self.settings.get("welcome_shown"):
            GLib.idle_add(self._show_welcome)

    def _show_welcome(self):
        dialog = Adw.Dialog()
        dialog.set_title(_("Welcome"))
        dialog.set_content_width(420)
        dialog.set_content_height(480)

        page = Adw.StatusPage()
        page.set_icon_name("x-office-document-symbolic")
        page.set_title(_("Welcome to Release Notes Editor"))
        page.set_description(_("Create release notes easily.\n\n"
            "✓ Release note templates\n"
            "✓ Markdown editor with preview\n"
            "✓ Version tracking\n"
            "✓ Translation-ready export\n"
            "✓ Multiple output formats"))

        btn = Gtk.Button(label=_("Get Started"))
        btn.add_css_class("suggested-action")
        btn.add_css_class("pill")
        btn.set_halign(Gtk.Align.CENTER)
        btn.set_margin_top(12)
        btn.connect("clicked", self._on_welcome_close, dialog)
        page.set_child(btn)

        box = Adw.ToolbarView()
        hb = Adw.HeaderBar()
        hb.set_show_title(False)
        box.add_top_bar(hb)
        box.set_content(page)
        dialog.set_child(box)
        dialog.present(self)

    def _on_welcome_close(self, btn, dialog):
        self.settings["welcome_shown"] = True
        _save_settings(self.settings)
        dialog.close()

    
    def _on_new(self, btn):
        dialog = Adw.AlertDialog()
        dialog.set_heading(_("New Release Notes"))
        dialog.set_body(_("Choose a template"))
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("standard", _("Standard"))
        dialog.add_response("security", _("Security Advisory"))
        dialog.set_response_appearance("standard", Adw.ResponseAppearance.SUGGESTED)
        
        def on_response(dlg, response):
            if response in TEMPLATES:
                self._editor.get_buffer().set_text(
                    TEMPLATES[response].format(project="ProjectName", version="1.0.0"))
        
        dialog.connect("response", on_response)
        dialog.present(self)

    def _on_open(self, btn):
        dialog = Gtk.FileDialog()
        dialog.set_title(_("Open Release Notes"))
        dialog.open(self, None, self._on_file_opened)

    def _on_file_opened(self, dialog, result):
        try:
            f = dialog.open_finish(result)
            path = f.get_path()
            with open(path) as fh:
                self._editor.get_buffer().set_text(fh.read())
            self._current_file = path
            self._title_widget.set_subtitle(os.path.basename(path))
        except:
            pass

    def _on_save(self, btn):
        if self._current_file:
            buf = self._editor.get_buffer()
            text = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), True)
            with open(self._current_file, "w") as f:
                f.write(text)
            ts = datetime.datetime.now().strftime("%H:%M:%S")
            self._status.set_text(_("%(time)s — Saved") % {"time": ts})
        else:
            dialog = Gtk.FileDialog()
            dialog.set_title(_("Save Release Notes"))
            dialog.set_initial_name("RELEASE-NOTES.md")
            dialog.save(self, None, self._on_save_done)

    def _on_save_done(self, dialog, result):
        try:
            f = dialog.save_finish(result)
            self._current_file = f.get_path()
            self._on_save(None)
        except:
            pass

    def _on_text_changed(self, buf):
        text = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), True)
        # Simple markdown-ish preview (strip # and format)
        preview_text = text
        self._preview.get_buffer().set_text(preview_text)


class ReleaseNotesEditorApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.window = None

        for name, callback in [
            ("settings", self._on_settings),
            ("copy-debug", self._on_copy_debug),
            ("shortcuts", self._on_shortcuts),
            ("about", self._on_about),
            ("quit", self._on_quit),
        ]:
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.add_action(action)

        self.set_accels_for_action("app.quit", ["<Ctrl>q"])
        self.set_accels_for_action("app.shortcuts", ["<Ctrl>slash"])

    def do_activate(self):
        if not self.window:
            self.window = ReleaseNotesEditorWindow(self)
        self.window.present()

    def _on_settings(self, *_args):
        if not self.window:
            return
        dialog = Adw.PreferencesDialog()
        dialog.set_title(_("Settings"))
        page = Adw.PreferencesPage()
        
        group = Adw.PreferencesGroup(title=_("Editor"))
        row = Adw.SwitchRow(title=_("Auto-save"))
        group.add(row)
        row2 = Adw.SwitchRow(title=_("Live preview"))
        row2.set_active(True)
        group.add(row2)
        page.add(group)
        dialog.add(page)
        dialog.present(self.window)

    def _on_copy_debug(self, *_args):
        if not self.window:
            return
        from . import __version__
        info = (
            f"Release Notes Editor {__version__}\n"
            f"Python {sys.version}\n"
            f"GTK {Gtk.MAJOR_VERSION}.{Gtk.MINOR_VERSION}\n"
            f"Adw {Adw.MAJOR_VERSION}.{Adw.MINOR_VERSION}\n"
            f"OS: {os.uname().sysname} {os.uname().release}\n"
        )
        clipboard = Gdk.Display.get_default().get_clipboard()
        clipboard.set(info)
        self.window._status.set_text(_("Debug info copied"))

    def _on_shortcuts(self, *_args):
        if self.window:
            dialog = Gtk.ShortcutsWindow(transient_for=self.window)
            section = Gtk.ShortcutsSection(visible=True)
            group = Gtk.ShortcutsGroup(title=_("General"), visible=True)
            for accel, title in [
                ("<Ctrl>q", _("Quit")),
                ("<Ctrl>slash", _("Keyboard shortcuts")),
            ]:
                group.append(Gtk.ShortcutsShortcut(accelerator=accel, title=title, visible=True))
            section.append(group)
            dialog.append(section)
            dialog.present()

    def _on_about(self, *_args):
        from . import __version__
        dialog = Adw.AboutDialog(
            application_name=_("Release Notes Editor"),
            application_icon="x-office-document-symbolic",
            version=__version__,
            developer_name="Daniel Nylander",
            website="https://github.com/yeager/release-notes-editor",
            license_type=Gtk.License.GPL_3_0,
            issue_url="https://github.com/yeager/release-notes-editor/issues",
            comments=_("Write and review release notes with template support and translation integration."),
        )
        dialog.present(self.window)

    def _on_quit(self, *_args):
        self.quit()


def main():
    app = ReleaseNotesEditorApp()
    app.run(sys.argv)
