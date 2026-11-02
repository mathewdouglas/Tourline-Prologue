"""GDI presentation matching launcher/preparation_ui.h's settings-style panel."""
import ctypes as C
from ctypes import wintypes as W
import math
import time


def rgb(r, g=None, b=None):
    return r | ((r if g is None else g) << 8) | ((r if b is None else b) << 16)


class Paint(C.Structure):
    _fields_ = [('dc', W.HDC), ('erase', W.BOOL), ('rect', W.RECT),
                ('restore', W.BOOL), ('update', W.BOOL), ('reserved', C.c_byte*32)]


class DrawItem(C.Structure):
    _fields_ = [('type', W.UINT), ('id', W.UINT), ('item', W.UINT), ('action', W.UINT),
                ('state', W.UINT), ('hwnd', W.HWND), ('dc', W.HDC), ('rect', W.RECT), ('data', C.c_size_t)]


class Theme:
    def __init__(self, ui, gdi):
        self.ui, self.gdi = ui, gdi
        for lib, name, result, args in (
            (ui, 'FillRect', C.c_int, [W.HDC, C.POINTER(W.RECT), W.HBRUSH]),
            (ui, 'BeginPaint', W.HDC, [W.HWND, C.POINTER(Paint)]),
            (ui, 'EndPaint', W.BOOL, [W.HWND, C.POINTER(Paint)]),
            (ui, 'DrawTextW', C.c_int, [W.HDC, W.LPCWSTR, C.c_int, C.POINTER(W.RECT), W.UINT]),
            (ui, 'InvalidateRect', W.BOOL, [W.HWND, C.POINTER(W.RECT), W.BOOL]),
            (ui, 'GetWindowTextW', C.c_int, [W.HWND, W.LPWSTR, C.c_int]),
            (ui, 'GetFocus', W.HWND, []),
            (ui, 'AdjustWindowRect', W.BOOL, [C.POINTER(W.RECT), W.DWORD, W.BOOL]),
            (ui, 'SetWindowPos', W.BOOL, [W.HWND, W.HWND, C.c_int, C.c_int, C.c_int, C.c_int, W.UINT]),
            (ui, 'SystemParametersInfoW', W.BOOL, [W.UINT, W.UINT, W.LPVOID, W.UINT]),
            (gdi, 'SetTextColor', W.DWORD, [W.HDC, W.DWORD]),
            (gdi, 'SetBkColor', W.DWORD, [W.HDC, W.DWORD]),
            (gdi, 'SetBkMode', C.c_int, [W.HDC, C.c_int]),
            (gdi, 'CreateSolidBrush', W.HBRUSH, [W.DWORD]),
            (gdi, 'DeleteObject', W.BOOL, [W.HANDLE]),
            (gdi, 'SelectObject', W.HANDLE, [W.HDC, W.HANDLE]),
            (gdi, 'CreateFontW', W.HFONT, [C.c_int]*5+[W.DWORD]*8+[W.LPCWSTR])):
            function = getattr(lib, name)
            function.restype, function.argtypes = result, args
        work = W.RECT()
        if not ui.SystemParametersInfoW(48, 0, C.byref(work), 0):
            work = W.RECT(0, 0, 1280, 720)
        self.work = work
        dpi = ui.GetDpiForSystem() if hasattr(ui,'GetDpiForSystem') else 96
        self.scale = min(dpi/96.0, (work.right-work.left-40)/760, (work.bottom-work.top-60)/480)
        self.scale = max(.5, self.scale)
        self.brushes, self.fonts = {}, {}
        self.panel = self.brush(rgb(28))
        self.field = self.brush(rgb(0, 4, 0))
        for key, size in (('title',22), ('row',19), ('help',15), ('note',13), ('button',21)):
            font = gdi.CreateFontW(-self.s(size), 0, 0, 0, 400, 0, 0, 0, 1, 0, 0, 4, 0, 'Segoe UI')
            if not font:
                self.close()
                raise C.WinError(C.get_last_error())
            self.fonts[key] = font

    def s(self, value):
        return round(value*self.scale)

    def brush(self, colour):
        if colour not in self.brushes:
            handle = self.gdi.CreateSolidBrush(colour)
            if not handle:
                raise C.WinError(C.get_last_error())
            self.brushes[colour] = handle
        return self.brushes[colour]

    def fill(self, dc, x0, y0, x1, y1, colour):
        rect = W.RECT(*(self.s(v) for v in (x0,y0,x1,y1)))
        self.ui.FillRect(dc, C.byref(rect), self.brush(colour))

    def position(self, hwnd, style):
        rect = W.RECT(0,0,self.s(740),self.s(446))
        if not self.ui.AdjustWindowRect(C.byref(rect), style, False):
            raise C.WinError(C.get_last_error())
        width,height=rect.right-rect.left,rect.bottom-rect.top
        x=self.work.left+(self.work.right-self.work.left-width)//2
        y=self.work.top+(self.work.bottom-self.work.top-height)//2
        self.ui.SetWindowPos(hwnd,None,x,y,width,height,0x14)

    def text(self, dc, font, text, rect, colour=190, flags=0x25):
        old=self.gdi.SelectObject(dc,self.fonts[font])
        self.gdi.SetTextColor(dc,rgb(colour));self.gdi.SetBkMode(dc,1)
        area=W.RECT(*(self.s(v) for v in rect))
        self.ui.DrawTextW(dc,text,-1,C.byref(area),flags|0x800)
        self.gdi.SelectObject(dc,old)

    def paint(self, hwnd, snapshot):
        ps=Paint();dc=self.ui.BeginPaint(hwnd,C.byref(ps))
        try:
            self.fill(dc,0,0,740,446,rgb(28))
            for y in range(60):
                t=y/60
                grey=45 if t<.04 else 27 if t<.1 else round(9-5*(t-.1)/.2) if t<.3 else round(4+24*(t-.3)/.7)
                self.fill(dc,0,y,740,y+1,rgb(grey))
            self.text(dc,'title','Collection verification',(0,12,740,46),178)
            for y in (68,382):self.fill(dc,0,y,740,y+1,rgb(76))
            for y in (142,238):
                for x in range(26,714,7):self.fill(dc,x,y,x+2,y+1,rgb(96))
            for top,bottom in ((88,132),(156,228),(254,286)):
                self.fill(dc,150,top,712,bottom,rgb(0,4,0))
                self.fill(dc,150,bottom-1,712,bottom,rgb(99,101,107))
            self.text(dc,'row','Stage',(26,88,132,120),190,0x26)
            self.text(dc,'row','Progress',(26,156,132,188),190,0x26)
            self.text(dc,'row','Elapsed',(26,254,132,286),190,0x26)
            self.fill(dc,28,306,712,322,rgb(0,4,0))
            counts=snapshot['counts'];done,total=counts.get('completed'),counts.get('total')
            if snapshot['outcome']=='complete':done,total=1,1
            if isinstance(done,int) and isinstance(total,int) and total>0 and 0<=done<=total:
                left,right=30,30+round(680*done/total)
            elif snapshot['outcome'] is None:
                shift=int(time.monotonic()*160)%816
                left,right=max(30,30+shift-136),min(710,30+shift)
            else:left=right=30
            if right>left:self.fill(dc,left,308,right,320,rgb(140 if snapshot['outcome']=='cancelled' else 204))
            self.fill(dc,28,321,712,322,rgb(99,101,107))
        finally:self.ui.EndPaint(hwnd,C.byref(ps))

    def colour(self, dc, field):
        colour=rgb(0,4,0) if field else rgb(28)
        self.gdi.SetTextColor(dc,rgb(204 if field else 150))
        self.gdi.SetBkColor(dc,colour)
        return self.field if field else self.panel

    def button(self, address):
        item=C.cast(address,C.POINTER(DrawItem)).contents
        dc,rect=item.dc,item.rect
        # Same three nested glass pill bands as preparation_ui.h.
        self.ui.FillRect(dc,C.byref(rect),self.panel)
        width=(rect.right-rect.left)/self.scale;height=(rect.bottom-rect.top)/self.scale
        focused=bool(item.state&0x10) or self.ui.GetFocus()==item.hwnd
        for inset in (0,1,3):
            radius=(height-2*inset)/2
            for y in range(inset,round(height-inset)):
                dy=y+.5-height/2
                half=math.sqrt(max(0,radius*radius-dy*dy))
                x0=round(inset+radius-half);x1=round(width-inset-radius+half)
                t=(y-inset)/max(1,height-2*inset)
                if inset==0:colour=rgb(46)
                elif inset==1:colour=rgb(168,0,0) if focused else rgb(0)
                elif t<.5:
                    u=t*2;colour=rgb(round(123-66*u),round(125-69*u),round(140-83*u))
                else:
                    u=(t-.5)*2;v=round(19-16*u/.6) if u<.6 else round(3+57*(u-.6)/.4);colour=rgb(v)
                self.fill(dc,x0,y,x1,y+1,colour)
        label=C.create_unicode_buffer(64);self.ui.GetWindowTextW(item.hwnd,label,len(label))
        self.text(dc,'button',label.value,(0,0,width,height),204)

    def close(self):
        for handle in list(self.fonts.values())+list(self.brushes.values()):self.gdi.DeleteObject(handle)
        self.fonts.clear();self.brushes.clear()
