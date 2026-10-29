"""Owner-only UI. Requires a signing key that never ships inside any exe."""
from pathlib import Path
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from .issuer import issue,generate_keys

def main():
    root=tk.Tk();root.title('鼠标跟随助手 · 授权签发');root.geometry('680x620')
    frame=ttk.Frame(root,padding=18);frame.pack(fill='both',expand=True)
    ttk.Label(frame,text='授权签发工具（仅管理员保管）',font=('Microsoft YaHei UI',16,'bold')).pack(anchor='w')
    ttk.Label(frame,text='激活码绑定设备，期限从签发时刻开始。私钥不要发送给使用者。',wraplength=620).pack(anchor='w',pady=10)
    key=tk.StringVar();device=tk.StringVar();plan=tk.StringVar(value='3 天体验')
    ttk.Label(frame,text='签发私钥文件：').pack(anchor='w');ttk.Entry(frame,textvariable=key).pack(fill='x',pady=4)
    actions=ttk.Frame(frame);actions.pack(fill='x')
    def choose():
        path=filedialog.askopenfilename(title='选择原有签发私钥',filetypes=[('PEM 密钥','*.pem'),('所有文件','*.*')])
        if path:key.set(path)
    def new_keys():
        path=filedialog.asksaveasfilename(title='首次部署：保存管理员私钥',initialfile='owner-private.pem',defaultextension='.pem')
        if not path:return
        private=Path(path);public=private.with_name('license-public.pem')
        try:generate_keys(private,public);key.set(str(private));messagebox.showinfo('密钥已生成',f'公钥：{public}\n客户端必须使用这份公钥重新构建。\n已经分发客户端时，请继续使用原私钥，不要另建新密钥。')
        except Exception as exc:messagebox.showerror('生成失败',str(exc))
    ttk.Button(actions,text='载入原私钥',command=choose).pack(side='left')
    ttk.Button(actions,text='首次部署时生成密钥',command=new_keys).pack(side='left',padx=8)
    ttk.Label(frame,text='使用者提供的设备码：').pack(anchor='w',pady=(18,4));ttk.Entry(frame,textvariable=device).pack(fill='x')
    ttk.Label(frame,text='授权类型：').pack(anchor='w',pady=(14,4));ttk.Combobox(frame,textvariable=plan,values=['3 天体验','30 天授权','永久授权'],state='readonly').pack(fill='x')
    ttk.Label(frame,text='生成的激活码：').pack(anchor='w',pady=(18,4));output=tk.Text(frame,height=10,wrap='char');output.pack(fill='both',expand=True)
    generated=['']
    def generate():
        try:
            generated[0]=issue(Path(key.get()),device.get(),{'3 天体验':'3d','30 天授权':'30d','永久授权':'permanent'}[plan.get()]);output.delete('1.0','end');output.insert('1.0',generated[0])
        except Exception as exc:messagebox.showerror('签发失败',str(exc))
    def copy():
        if not generated[0]:return
        root.clipboard_clear();root.clipboard_append(generated[0]);messagebox.showinfo('已复制','将此激活码发送给对应设备的使用者即可。')
    row=ttk.Frame(frame);row.pack(fill='x',pady=12)
    ttk.Button(row,text='生成激活码',command=generate).pack(side='left');ttk.Button(row,text='复制激活码',command=copy).pack(side='left',padx=8)
    root.mainloop()
