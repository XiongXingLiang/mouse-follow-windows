from __future__ import annotations
import json,logging,platform,queue,tkinter as tk
from pathlib import Path
from tkinter import ttk,messagebox,filedialog
from .windows_input import enable_dpi_awareness
from .license_core import LicenseError
from .license_store import LicenseManager,device_code,data_dir
from .paths import ASSETS

def main(*,license_factory=None,owner_edition=False):
    enable_dpi_awareness();root=tk.Tk();root.title('鼠标跟随助手 · 管理员永久版' if owner_edition else '鼠标跟随助手');root.title(root.title()+' · 性能版 10.30');root.geometry('620x790');root.minsize(580,680)
    if platform.system()!='Windows':messagebox.showerror('仅支持 Windows','请在 Windows 10/11 64 位系统运行。');root.destroy();return
    logging.basicConfig(filename=data_dir()/'app.log',level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    try:
        if license_factory is None:
            public=(ASSETS/'license-public.pem').read_bytes();device=device_code();manager=LicenseManager(public,device)
        else:
            manager=license_factory();device=''
    except Exception as exc:messagebox.showerror('启动失败',str(exc));root.destroy();return
    from .runtime import Runtime
    from .detection import Region
    from PIL import Image,ImageTk
    runtime=Runtime(manager);runtime.start();status=tk.StringVar(value='管理员永久版，可直接开始监测' if owner_edition else '请激活后开始监测');license_text=tk.StringVar(value='尚未激活')
    if manager.grant:license_text.set(manager.grant.description)
    elif manager.error:license_text.set(manager.error)
    frame=ttk.Frame(root,padding=16);frame.pack(fill='both',expand=True)
    ttk.Label(frame,text='鼠标跟随助手 · 管理员版' if owner_edition else '鼠标跟随助手',font=('Microsoft YaHei UI',18,'bold')).pack(anchor='w')
    ttk.Label(frame,textvariable=license_text,wraplength=550).pack(anchor='w',pady=(6,12))
    if owner_edition:
        ttk.Label(frame,text='管理员自用 · 永久使用 · 无需设备码或激活码').pack(anchor='w')
    else:
        ttk.Label(frame,text='本机设备码（发送给授权签发者）：').pack(anchor='w')
        code=ttk.Entry(frame);code.insert(0,device);code.configure(state='readonly');code.pack(fill='x',pady=4)
        buttons=ttk.Frame(frame);buttons.pack(fill='x')
        def copy_device():root.clipboard_clear();root.clipboard_append(device);status.set('设备码已复制')
        def activate():
            runtime.stop();dialog=tk.Toplevel(root);dialog.title('导入激活码');dialog.geometry('560x280');dialog.transient(root)
            ttk.Label(dialog,text='粘贴你收到的激活码：').pack(anchor='w',padx=12,pady=10)
            text=tk.Text(dialog,height=8,wrap='char');text.pack(fill='both',expand=True,padx=12)
            def submit():
                try:grant=manager.activate(text.get('1.0','end').strip());license_text.set(grant.description);status.set('激活成功');dialog.destroy()
                except Exception as exc:messagebox.showerror('激活失败',str(exc),parent=dialog)
            ttk.Button(dialog,text='激活',command=submit).pack(pady=10)
        ttk.Button(buttons,text='复制设备码',command=copy_device).pack(side='left')
        ttk.Button(buttons,text='导入激活码',command=activate).pack(side='left',padx=8)
    ttk.Separator(frame).pack(fill='x',pady=14)
    from mss import mss
    with mss() as s:monitors=[dict(m) for m in s.monitors[1:]]
    monitor_var=tk.StringVar();combo=ttk.Combobox(frame,textvariable=monitor_var,state='readonly',values=[f'显示器 {i+1} · {m["width"]}×{m["height"]}' for i,m in enumerate(monitors)]);combo.current(0);combo.pack(fill='x')
    region_text=tk.StringVar(value='自动识别游戏窗口');manual=None
    def change_monitor(event=None):
        nonlocal manual
        manual=None;runtime.configure(combo.current()+1);region_text.set('自动识别游戏窗口')
    combo.bind('<<ComboboxSelected>>',change_monitor)
    ttk.Label(frame,textvariable=region_text).pack(anchor='w',pady=5)
    region_buttons=ttk.Frame(frame);region_buttons.pack(fill='x')
    def select_region():
        nonlocal manual
        runtime.stop();monitor=monitors[combo.current()]
        with mss(with_cursor=False) as s:shot=s.grab(monitor);image=Image.frombytes('RGB',shot.size,shot.rgb)
        scale=min(900/image.width,600/image.height,1.);shown=image.resize((round(image.width*scale),round(image.height*scale)))
        dialog=tk.Toplevel(root);dialog.title('拖动框选小游戏内部石头画面（不要包含标题栏）');canvas=tk.Canvas(dialog,width=shown.width,height=shown.height,highlightthickness=0);canvas.pack();photo=ImageTk.PhotoImage(shown);canvas.image=photo;canvas.create_image(0,0,anchor='nw',image=photo)
        points=[];rect=[None]
        def down(e):
            points[:]=[e.x,e.y]
            if rect[0]:canvas.delete(rect[0])
            rect[0]=canvas.create_rectangle(e.x,e.y,e.x,e.y,outline='#33bbee',width=2)
        def drag(e):
            if points:canvas.coords(rect[0],points[0],points[1],e.x,e.y)
        def up(e):
            nonlocal manual
            if not points:return
            x0,x1=sorted([points[0],e.x]);y0,y1=sorted([points[1],e.y]);candidate=Region(round(x0/scale),round(y0/scale),round((x1-x0)/scale),round((y1-y0)/scale))
            if candidate.width<120 or candidate.height<100:messagebox.showerror('区域过小','请重新框选完整的小游戏内部画面',parent=dialog);return
            manual=candidate;runtime.configure(combo.current()+1,manual);region_text.set(f'手动区域：{manual.width}×{manual.height}');dialog.destroy()
        canvas.bind('<ButtonPress-1>',down);canvas.bind('<B1-Motion>',drag);canvas.bind('<ButtonRelease-1>',up)
    ttk.Button(region_buttons,text='手动框选画面',command=select_region).pack(side='left')
    ttk.Button(region_buttons,text='恢复自动识别',command=change_monitor).pack(side='left',padx=8)
    move=tk.BooleanVar(value=False)
    def change_mode():
        runtime.stop()
        if move.get():runtime.move_enabled.set()
        else:runtime.move_enabled.clear()
        status.set('模式已切换，请重新开始监测')
    ttk.Checkbutton(frame,text='启用真实鼠标跟随（未勾选时仅预览）',variable=move,command=change_mode).pack(anchor='w',pady=(14,8))
    controls=ttk.Frame(frame);controls.pack(fill='x')
    def arm():
        try:
            runtime.arm();status.set('开始监测，等待游戏画面和白色目标')
            if move.get():root.iconify()
        except Exception as exc:messagebox.showerror('无法开始',str(exc))
    ttk.Button(controls,text='开始监测',command=arm).pack(side='left')
    ttk.Button(controls,text='停止',command=lambda:(runtime.stop(),status.set('已停止'))).pack(side='left',padx=8)
    ttk.Label(frame,text='Esc 紧急停止 · F8 暂停 / 恢复',foreground='#7b3a20').pack(anchor='w',pady=8)
    ttk.Label(frame,textvariable=status,wraplength=550).pack(anchor='w',pady=5)
    preview=ttk.Label(frame,anchor='center');preview.pack(fill='both',expand=True)
    def poll():
        try:
            while True:
                event=runtime.events.get_nowait();status.set(event['text'])
                if event['preview'] is not None:
                    image=Image.fromarray(event['preview'][:,:,::-1]);photo=ImageTk.PhotoImage(image);preview.configure(image=photo);preview.image=photo
        except queue.Empty:pass
        if not runtime.shutdown.is_set():root.after(60,poll)
    def close():runtime.close();root.after(80,root.destroy)
    root.protocol('WM_DELETE_WINDOW',close);root.after(60,poll);root.mainloop()
