"""Offline electronics inventory. Run with Python 3.10+: python app.py"""
import csv
import os
import shutil
import sqlite3
import subprocess
import sys
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

APP_DIR = Path(os.getenv('LOCALAPPDATA', Path.home())) / 'ElectronicsInventory'
DB = APP_DIR / 'inventory.db'
FIELDS = ('name', 'category', 'part_number', 'value', 'package', 'quantity', 'min_quantity', 'location', 'datasheet', 'notes')
CATEGORIES = ('Resistors', 'Capacitors', 'Inductors', 'Diodes', 'Transistors', 'Integrated Circuits', 'Sensors', 'Modules', 'Connectors', 'Switches', 'Power', 'Tools & Equipment', 'Other')


def connect():
    APP_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys=ON')
    con.execute('''CREATE TABLE IF NOT EXISTS parts (
        id INTEGER PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL DEFAULT 'Other',
        part_number TEXT NOT NULL DEFAULT '', value TEXT NOT NULL DEFAULT '',
        package TEXT NOT NULL DEFAULT '', quantity INTEGER NOT NULL DEFAULT 0 CHECK(quantity>=0),
        min_quantity INTEGER NOT NULL DEFAULT 0 CHECK(min_quantity>=0),
        location TEXT NOT NULL DEFAULT '', datasheet TEXT NOT NULL DEFAULT '',
        notes TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL)''')
    con.execute('''CREATE TABLE IF NOT EXISTS movements (
        id INTEGER PRIMARY KEY, part_id INTEGER NOT NULL REFERENCES parts(id) ON DELETE CASCADE,
        delta INTEGER NOT NULL, reason TEXT NOT NULL, timestamp TEXT NOT NULL)''')
    con.commit()
    return con


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Circuit Shelf | Electronics Inventory')
        self.geometry('1200x720')
        self.minsize(930, 570)
        self.con = connect()
        self.selected = None
        self.configure(bg='#101827')
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('Treeview', background='#172437', foreground='#eef4fa', fieldbackground='#172437', rowheight=28, borderwidth=0)
        style.configure('Treeview.Heading', background='#263951', foreground='#ffffff', font=('Segoe UI', 10, 'bold'))
        style.map('Treeview', background=[('selected', '#146b75')])
        style.configure('TCombobox', padding=4)
        self.build()
        self.refresh()
        self.protocol('WM_DELETE_WINDOW', self.close)

    def build(self):
        bar = tk.Frame(self, bg='#101827', padx=16, pady=12)
        bar.pack(fill='x')
        tk.Label(bar, text='CIRCUIT SHELF', font=('Segoe UI', 19, 'bold'), fg='#65e5c4', bg='#101827').pack(side='left')
        tk.Label(bar, text='  •  Offline lab archive', fg='#9bb0c7', bg='#101827').pack(side='left')
        for label, cmd in [('Backup', self.backup), ('Export CSV', self.export_csv), ('Import CSV', self.import_csv)]:
            tk.Button(bar, text=label, command=cmd, bg='#263951', fg='white', relief='flat', padx=10).pack(side='right', padx=3)
        filters = tk.Frame(self, bg='#101827', padx=16, pady=5)
        filters.pack(fill='x')
        self.query = tk.StringVar()
        self.query.trace_add('write', lambda *_: self.refresh())
        tk.Entry(filters, textvariable=self.query, font=('Segoe UI', 11), bg='#203047', fg='white', insertbackground='white', relief='flat').pack(side='left', fill='x', expand=True, ipady=7)
        self.category_filter = tk.StringVar(value='All categories')
        cats = ttk.Combobox(filters, textvariable=self.category_filter, values=('All categories',) + CATEGORIES, state='readonly', width=22)
        cats.pack(side='left', padx=8)
        cats.bind('<<ComboboxSelected>>', lambda _: self.refresh())
        self.low_only = tk.BooleanVar()
        tk.Checkbutton(filters, text='Low stock', variable=self.low_only, command=self.refresh, bg='#101827', fg='white', selectcolor='#263951', activebackground='#101827').pack(side='left')
        body = tk.PanedWindow(self, orient='horizontal', bg='#101827', sashwidth=6)
        body.pack(fill='both', expand=True, padx=16, pady=8)
        left = tk.Frame(body, bg='#172437')
        right = tk.Frame(body, bg='#172437', padx=12, pady=10)
        body.add(left, minsize=480)
        body.add(right, minsize=340)
        cols = ('name', 'category', 'part_number', 'value', 'quantity', 'location')
        self.tree = ttk.Treeview(left, columns=cols, show='headings', selectmode='browse')
        for c, w in zip(cols, (180, 130, 125, 95, 70, 150)):
            self.tree.heading(c, text=c.replace('_', ' ').title())
            self.tree.column(c, width=w, minwidth=65)
        self.tree.tag_configure('low', foreground='#ffbc80')
        ys = ttk.Scrollbar(left, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=ys.set)
        self.tree.pack(side='left', fill='both', expand=True)
        ys.pack(side='right', fill='y')
        self.tree.bind('<<TreeviewSelect>>', self.select)
        self.tree.bind('<Double-1>', lambda _: self.adjust())
        tk.Label(right, text='COMPONENT RECORD', bg='#172437', fg='#65e5c4', font=('Segoe UI', 13, 'bold')).pack(anchor='w', pady=(0, 8))
        self.vars = {}
        for field in FIELDS:
            row = tk.Frame(right, bg='#172437')
            row.pack(fill='x', pady=3)
            tk.Label(row, text=field.replace('_', ' ').title(), bg='#172437', fg='#d7e4ef', width=15, anchor='w').pack(side='left')
            var = tk.StringVar()
            self.vars[field] = var
            if field == 'category':
                widget = ttk.Combobox(row, textvariable=var, values=CATEGORIES)
            else:
                widget = tk.Entry(row, textvariable=var, bg='#203047', fg='white', insertbackground='white', relief='flat')
            widget.pack(side='left', fill='x', expand=True, ipady=4)
        buttons = tk.Frame(right, bg='#172437')
        buttons.pack(fill='x', pady=12)
        for label, cmd in [('New', self.clear), ('Save', self.save), ('Adjust stock', self.adjust), ('Delete', self.delete)]:
            tk.Button(buttons, text=label, command=cmd, bg='#146b75', fg='white', relief='flat', padx=8).pack(side='left', padx=3)
        self.history = tk.Text(right, height=7, bg='#203047', fg='#d7e4ef', relief='flat', state='disabled', wrap='word')
        tk.Label(right, text='STOCK HISTORY', bg='#172437', fg='#65e5c4', font=('Segoe UI', 10, 'bold')).pack(anchor='w')
        self.history.pack(fill='both', expand=True, pady=5)
        self.status = tk.Label(self, bg='#101827', fg='#9bb0c7', anchor='w', padx=16, pady=7)
        self.status.pack(fill='x')
        self.clear()

    def refresh(self):
        search = '%' + self.query.get().strip() + '%'
        sql = '''SELECT * FROM parts WHERE (name LIKE ? OR category LIKE ? OR part_number LIKE ? OR value LIKE ? OR location LIKE ? OR notes LIKE ?)'''
        args = [search] * 6
        if self.category_filter.get() != 'All categories':
            sql += ' AND category = ?'
            args.append(self.category_filter.get())
        if self.low_only.get():
            sql += ' AND quantity <= min_quantity'
        sql += ' ORDER BY category COLLATE NOCASE, name COLLATE NOCASE, id'
        current = self.selected
        self.tree.delete(*self.tree.get_children())
        rows = self.con.execute(sql, args).fetchall()
        for row in rows:
            self.tree.insert('', 'end', iid=str(row['id']), values=tuple(row[c] for c in ('name', 'category', 'part_number', 'value', 'quantity', 'location')), tags=('low',) if row['quantity'] <= row['min_quantity'] else ())
        if current is not None and self.tree.exists(str(current)):
            self.tree.selection_set(str(current))
        low = self.con.execute('SELECT count(*) FROM parts WHERE quantity <= min_quantity').fetchone()[0]
        self.status.config(text=f'{len(rows)} shown  •  {low} low stock  •  Data: {DB}')

    def select(self, _=None):
        selection = self.tree.selection()
        if not selection:
            return
        self.selected = int(selection[0])
        row = self.con.execute('SELECT * FROM parts WHERE id=?', (self.selected,)).fetchone()
        if not row:
            return
        for f in FIELDS:
            self.vars[f].set(str(row[f]))
        movements = self.con.execute('SELECT * FROM movements WHERE part_id=? ORDER BY id DESC LIMIT 30', (self.selected,)).fetchall()
        self.history.config(state='normal')
        self.history.delete('1.0', 'end')
        for m in movements:
            self.history.insert('end', f"{m['timestamp']}  {m['delta']:+d}  {m['reason']}\n")
        self.history.config(state='disabled')

    def clear(self):
        self.selected = None
        self.tree.selection_remove(self.tree.selection())
        for var in self.vars.values():
            var.set('')
        self.vars['category'].set('Other')
        self.vars['quantity'].set('0')
        self.vars['min_quantity'].set('0')
        self.history.config(state='normal')
        self.history.delete('1.0', 'end')
        self.history.config(state='disabled')

    def save(self):
        data = {f: self.vars[f].get().strip() for f in FIELDS}
        if not data['name']:
            messagebox.showerror('Missing name', 'Enter a component name.')
            return
        try:
            for f in ('quantity', 'min_quantity'):
                data[f] = int(data[f])
                if data[f] < 0:
                    raise ValueError
        except ValueError:
            messagebox.showerror('Invalid quantity', 'Quantity and minimum must be whole numbers ≥ 0.')
            return
        now = datetime.now().isoformat(timespec='seconds')
        with self.con:
            if self.selected is None:
                cur = self.con.execute('INSERT INTO parts (' + ','.join(FIELDS) + ',updated_at) VALUES (' + ','.join('?' for _ in FIELDS) + ',?)', (*[data[f] for f in FIELDS], now))
                self.selected = cur.lastrowid
                delta = data['quantity']
                reason = 'Initial stock'
            else:
                old = self.con.execute('SELECT quantity FROM parts WHERE id=?', (self.selected,)).fetchone()
                if old is None:
                    self.clear()
                    return
                delta = data['quantity'] - old['quantity']
                reason = 'Edited quantity'
                self.con.execute('UPDATE parts SET ' + ','.join(f + '=?' for f in FIELDS) + ',updated_at=? WHERE id=?', (*[data[f] for f in FIELDS], now, self.selected))
            if delta:
                self.con.execute('INSERT INTO movements (part_id,delta,reason,timestamp) VALUES (?,?,?,?)', (self.selected, delta, reason, now))
        self.refresh()
        self.tree.selection_set(str(self.selected))
        self.select()

    def adjust(self):
        if self.selected is None:
            messagebox.showinfo('Select a record', 'Select and save a component first.')
            return
        dlg = tk.Toplevel(self)
        dlg.title('Adjust stock')
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.grab_set()
        tk.Label(dlg, text='Change (+ to add, − to use):').pack(padx=16, pady=(12, 2))
        amount = tk.Entry(dlg)
        amount.pack(padx=16)
        tk.Label(dlg, text='Reason / project:').pack(padx=16, pady=(8, 2))
        reason = tk.Entry(dlg, width=38)
        reason.pack(padx=16)
        def apply():
            try:
                delta = int(amount.get())
                old = self.con.execute('SELECT quantity FROM parts WHERE id=?', (self.selected,)).fetchone()['quantity']
                if not delta or old + delta < 0:
                    raise ValueError
            except (ValueError, TypeError):
                messagebox.showerror('Invalid change', 'Enter a nonzero whole number without making stock negative.', parent=dlg)
                return
            now = datetime.now().isoformat(timespec='seconds')
            with self.con:
                self.con.execute('UPDATE parts SET quantity=quantity+?,updated_at=? WHERE id=?', (delta, now, self.selected))
                self.con.execute('INSERT INTO movements (part_id,delta,reason,timestamp) VALUES (?,?,?,?)', (self.selected, delta, reason.get().strip() or 'Stock adjustment', now))
            dlg.destroy()
            self.refresh()
            self.tree.selection_set(str(self.selected))
            self.select()
        tk.Button(dlg, text='Apply', command=apply).pack(pady=12)
        amount.focus_set()

    def delete(self):
        if self.selected is None:
            return
        if messagebox.askyesno('Delete record?', 'Delete this component and its stock history permanently?'):
            with self.con:
                self.con.execute('DELETE FROM parts WHERE id=?', (self.selected,))
            self.clear()
            self.refresh()

    def backup(self):
        path = filedialog.asksaveasfilename(title='Back up database', defaultextension='.db', initialfile='electronics-inventory-' + datetime.now().strftime('%Y%m%d') + '.db', filetypes=[('SQLite database', '*.db')])
        if path:
            with sqlite3.connect(path) as target:
                self.con.backup(target)
            messagebox.showinfo('Backup saved', path)

    def export_csv(self):
        path = filedialog.asksaveasfilename(defaultextension='.csv', initialfile='electronics-inventory.csv', filetypes=[('CSV', '*.csv')])
        if path:
            with open(path, 'w', newline='', encoding='utf-8-sig') as out:
                writer = csv.writer(out)
                writer.writerow(FIELDS)
                for row in self.con.execute('SELECT * FROM parts ORDER BY id'):
                    writer.writerow([row[f] for f in FIELDS])
            messagebox.showinfo('Export complete', path)

    def import_csv(self):
        path = filedialog.askopenfilename(filetypes=[('CSV', '*.csv')])
        if not path:
            return
        try:
            with open(path, newline='', encoding='utf-8-sig') as inp:
                reader = csv.DictReader(inp)
                if not reader.fieldnames or not {'name', 'quantity'}.issubset(reader.fieldnames):
                    raise ValueError('CSV needs name and quantity columns.')
                records = []
                for number, row in enumerate(reader, 2):
                    item = {f: (row.get(f) or '').strip() for f in FIELDS}
                    if not item['name']:
                        raise ValueError(f'Row {number}: name is missing.')
                    for f in ('quantity', 'min_quantity'):
                        item[f] = int(item[f] or 0)
                        if item[f] < 0:
                            raise ValueError(f'Row {number}: negative {f}.')
                    item['category'] = item['category'] or 'Other'
                    records.append(item)
            if not messagebox.askyesno('Import records?', f'Add {len(records)} records? Existing records will be kept; duplicate rows may be added.'):
                return
            now = datetime.now().isoformat(timespec='seconds')
            with self.con:
                for item in records:
                    cur = self.con.execute('INSERT INTO parts (' + ','.join(FIELDS) + ',updated_at) VALUES (' + ','.join('?' for _ in FIELDS) + ',?)', (*[item[f] for f in FIELDS], now))
                    if item['quantity']:
                        self.con.execute('INSERT INTO movements (part_id,delta,reason,timestamp) VALUES (?,?,?,?)', (cur.lastrowid, item['quantity'], 'CSV import', now))
            self.refresh()
            messagebox.showinfo('Import complete', f'Added {len(records)} records.')
        except (OSError, ValueError, csv.Error) as exc:
            messagebox.showerror('Import failed', str(exc))

    def close(self):
        self.con.close()
        self.destroy()


if __name__ == '__main__':
    App().mainloop()
