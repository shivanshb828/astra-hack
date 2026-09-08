import Cocoa
import SwiftUI
import WebKit

struct ChatMessage: Identifiable { let id=UUID();let text:String;let user:Bool }
final class ChatModel: ObservableObject {
 @Published var messages=[ChatMessage(text:"Choose the application above.\nKiCad: inspect, move a component, or apply the cached layout.\nBlender: inspect the scene, check constraints, or focus a component.",user:false)]
 @Published var input=""
 @Published var target="KiCad" { didSet { status="\(target) · local commands" } }
 @Published var busy=false
 @Published var status="Live KiCad · local commands"
 func send(_ supplied:String?=nil){
  let text=(supplied ?? input).trimmingCharacters(in:.whitespacesAndNewlines)
  guard !text.isEmpty && !busy else{return}
  let requestTarget=target
  input="";messages.append(ChatMessage(text:"\(requestTarget) · \(text)",user:true));busy=true;status="Working in \(requestTarget)…"
  guard let token=Bundle.main.object(forInfoDictionaryKey:"MissionPCBToken") as? String else {finish("Connection configuration is missing. Relaunch using the MissionPCB launcher.",ok:false);return}
  var request=URLRequest(url:URL(string:"http://127.0.0.1:8768/command")!);request.httpMethod="POST";request.timeoutInterval=20
  request.setValue(token,forHTTPHeaderField:"X-Widget-Token");request.httpBody=(requestTarget == "Blender" ? "blender: " + text : text).data(using:.utf8)
  URLSession.shared.dataTask(with:request){data,response,error in
   let code=(response as? HTTPURLResponse)?.statusCode ?? 0
   var message=String(data:data ?? Data(),encoding:.utf8) ?? "No response from \(requestTarget)."
   if error != nil {message="The local bridge isn't responding. Open the MissionPCB dashboard or restart the bridge, then try again. Your command may not have completed; inspect the current state before retrying."}
   else if code==403 {message="The panel and bridge have different connection credentials. Relaunch them together to reconnect."}
   else if code != 200 {message="The bridge couldn't complete this request. Inspect the current state before retrying."}
   DispatchQueue.main.async{self.finish(message,ok:error==nil && code==200 && !message.hasPrefix("Could not apply"))}
  }.resume()
 }
 func finish(_ text:String,ok:Bool){messages.append(ChatMessage(text:text,user:false));busy=false;status=ok ? "\(target) · local commands" : "Connection needs attention"}
}
struct ReviewDashboard: NSViewRepresentable {
 func makeNSView(context:Context)->WKWebView {
  let view=WKWebView();view.load(URLRequest(url:URL(string:"http://127.0.0.1:8768/")!));return view
 }
 func updateNSView(_ view:WKWebView,context:Context){}
}
struct ChatView: View {
 @ObservedObject var model:ChatModel
 @State private var compact=true
 @State private var dashboard=false
 @Environment(\.accessibilityReduceMotion) var reduceMotion
 var body: some View {
 VStack(spacing:0){
  if dashboard {
   HStack {
    Button("← Chat"){dashboard=false;NotificationCenter.default.post(name:Notification.Name("MissionPCBExpand"),object:nil)}
    Spacer()
    Button("Collapse"){dashboard=false;compact=true;NotificationCenter.default.post(name:Notification.Name("MissionPCBCollapse"),object:nil)}
   }.buttonStyle(.plain).padding(14)
   ReviewDashboard()
  } else if compact {
   Button {
    compact=false;dashboard=true
    NotificationCenter.default.post(name:Notification.Name("MissionPCBDashboard"),object:nil)
   } label: {
    HStack(spacing:12){
     Circle().fill(model.busy ? Color(red:0.78,green:0.9,blue:0.42) : Color(red:0.35,green:0.42,blue:0.34)).frame(width:8,height:8)
     VStack(alignment:.leading,spacing:4){
      Text("MissionPCB").font(.system(size:16,weight:.semibold))
      Text(model.busy ? model.status : "Open board review").font(.system(size:14)).foregroundStyle(.secondary).lineLimit(1)
     }
     Spacer()
     Image(systemName:"chevron.up").font(.system(size:11,weight:.medium)).foregroundStyle(.secondary)
    }.padding(.horizontal,24).frame(maxWidth:.infinity,maxHeight:.infinity).contentShape(Rectangle())
   }.buttonStyle(.plain).accessibilityLabel("Expand MissionPCB dashboard")
  } else {
  HStack(spacing:10){ZStack{RoundedRectangle(cornerRadius:11).fill(Color(red:0.78,green:0.9,blue:0.42).opacity(0.15)).frame(width:35,height:35);Image(systemName:"waveform.path.ecg").foregroundStyle(Color(red:0.22,green:0.30,blue:0.15))}
   VStack(alignment:.leading,spacing:3){Text("MissionPCB").font(.system(size:14,weight:.semibold));Text(model.status).font(.system(size:10)).foregroundStyle(.secondary)}
   Spacer();Button {
    compact=true
    NotificationCenter.default.post(name:Notification.Name("MissionPCBCollapse"),object:nil)
   } label: {Image(systemName:"chevron.down").foregroundStyle(.secondary)}.buttonStyle(.plain).help("Collapse to status card")
   Button{dashboard=true;NotificationCenter.default.post(name:Notification.Name("MissionPCBDashboard"),object:nil)}label:{Image(systemName:"arrow.up.right.square").foregroundStyle(.secondary)}.buttonStyle(.plain).help("Expand to full review dashboard")
  }.padding(.horizontal,20).padding(.top,17).padding(.bottom,13)
  Picker("Application",selection:$model.target){Text("KiCad").tag("KiCad");Text("Blender").tag("Blender")}.pickerStyle(.segmented).disabled(model.busy).padding(.horizontal,20).padding(.bottom,10)
  Divider().opacity(0.2)
  ScrollViewReader{proxy in ScrollView{
   VStack(alignment:.leading,spacing:17){ForEach(model.messages){message in
    HStack{if message.user{Spacer(minLength:40)}
     Text(message.text).font(.system(size:12)).lineSpacing(5).textSelection(.enabled).padding(message.user ? 12 : 3).background(message.user ? Color(red:0.92,green:1,blue:0.69) : Color.clear,in:RoundedRectangle(cornerRadius:15)).frame(maxWidth:360,alignment:.leading)
     if !message.user{Spacer(minLength:10)}
    }.id(message.id)
   }
   if model.busy{HStack(spacing:8){ProgressView().controlSize(.small);Text(model.target == "Blender" ? "Working with your scene…" : "Working with your board…").font(.system(size:11)).foregroundStyle(.secondary)}.id("working")}
   }.padding(18)
  }.onChange(of:model.messages.count){_ in if reduceMotion {proxy.scrollTo(model.messages.last?.id,anchor:.bottom)}else{withAnimation(.easeOut(duration:0.2)){proxy.scrollTo(model.messages.last?.id,anchor:.bottom)}}}
  }
  HStack(spacing:7){suggestion(model.target == "Blender" ? "Inspect scene" : "Inspect board",model.target == "Blender" ? "Inspect" : "Inspect the board");suggestion("Full check","Full check");suggestion(model.target == "Blender" ? "Focus sensor" : "Reset",model.target == "Blender" ? "Focus sensor" : "Reset the layout");Spacer()}.padding(.horizontal,17).padding(.bottom,12)
  HStack(alignment:.center,spacing:10){TextField(model.target == "Blender" ? "Inspect, check, or focus a component…" : "Enter a board command…",text:$model.input).textFieldStyle(.plain).font(.system(size:13)).onSubmit{model.send()}.accessibilityLabel("Message MissionPCB")
   Button{model.send()}label:{Image(systemName:"arrow.up").font(.system(size:14,weight:.semibold)).frame(width:30,height:30).background(model.input.isEmpty || model.busy ? Color.black.opacity(0.08) : Color(red:0.78,green:0.9,blue:0.42),in:Circle()).foregroundStyle(model.input.isEmpty || model.busy ? Color.gray : Color.black)}.buttonStyle(.plain).disabled(model.input.isEmpty || model.busy).accessibilityLabel("Send message")
  }.padding(13).background(Color.white,in:RoundedRectangle(cornerRadius:19)).overlay(RoundedRectangle(cornerRadius:19).stroke(Color(red:0.78,green:0.9,blue:0.42).opacity(model.busy ? 0.5 : 0.18),lineWidth:1)).shadow(color:Color(red:0.78,green:0.9,blue:0.42).opacity(model.busy ? 0.12 : 0.035),radius:12).animation(reduceMotion ? nil : .easeInOut(duration:0.25),value:model.busy).padding(.horizontal,15)
  Text("Local board commands").font(.system(size:9)).foregroundStyle(.secondary).padding(.vertical,12)
 }
 }.foregroundStyle(Color(red:0.10,green:0.12,blue:0.10)).background(Color(red:0.965,green:0.97,blue:0.957)).clipShape(RoundedRectangle(cornerRadius:compact ? 38 : 20)).overlay(RoundedRectangle(cornerRadius:compact ? 38 : 20).stroke(LinearGradient(colors:[Color(red:0.78,green:0.9,blue:0.42).opacity(0.35),Color.black.opacity(0.06)],startPoint:.topLeading,endPoint:.bottomTrailing),lineWidth:1)).preferredColorScheme(.light)
 }
 func suggestion(_ label:String,_ command:String)->some View {Button(label){model.send(command)}.buttonStyle(.plain).font(.system(size:10)).padding(.horizontal,10).padding(.vertical,7).background(Color.white,in:Capsule()).overlay(Capsule().stroke(Color.black.opacity(0.06))).disabled(model.busy)}
}
final class FloatingPanel:NSPanel{override var canBecomeKey:Bool{true};override var canBecomeMain:Bool{false}}
final class Controller:NSObject,NSApplicationDelegate {
 var panel:FloatingPanel!;let model=ChatModel()
 func applicationDidFinishLaunching(_ notification:Notification){let screen=NSScreen.main!.visibleFrame
  panel=FloatingPanel(contentRect:NSRect(x:screen.midX-235,y:screen.minY+16,width:470,height:86),styleMask:[.titled,.closable,.fullSizeContentView,.nonactivatingPanel,.resizable],backing:.buffered,defer:false)
  panel.title="MissionPCB Assistant";panel.titleVisibility = .hidden;panel.titlebarAppearsTransparent=true;panel.level = .floating;panel.collectionBehavior=[.canJoinAllSpaces,.fullScreenAuxiliary];panel.hidesOnDeactivate=false;panel.isMovableByWindowBackground=true;panel.isReleasedWhenClosed=false;panel.minSize=NSSize(width:390,height:86);panel.isOpaque=false;panel.backgroundColor = .clear;panel.hasShadow=true
  NotificationCenter.default.addObserver(forName:Notification.Name("MissionPCBDashboard"),object:nil,queue:.main){[weak self] _ in self?.resizePanel(height:760,width:1100)}
  NotificationCenter.default.addObserver(forName:Notification.Name("MissionPCBExpand"),object:nil,queue:.main){[weak self] _ in self?.resizePanel(height:420)}
  NotificationCenter.default.addObserver(forName:Notification.Name("MissionPCBCollapse"),object:nil,queue:.main){[weak self] _ in self?.resizePanel(height:86)}
  panel.contentView=NSHostingView(rootView:ChatView(model:model));panel.makeKeyAndOrderFront(nil);NSApp.activate(ignoringOtherApps:true)
 }
 func resizePanel(height:CGFloat,width:CGFloat=470){
  let screen=(panel.screen ?? NSScreen.main)!.visibleFrame
  var frame=panel.frame
  let center=frame.midX
  frame.size=NSSize(width:min(width,screen.width-32),height:min(height,screen.height-32))
  frame.origin.x=max(screen.minX+16,min(center-frame.width/2,screen.maxX-frame.width-16))
  frame.origin.y=max(screen.minY+16,min(frame.minY,screen.maxY-frame.height-16))
  panel.setFrame(frame,display:true,animate:!NSWorkspace.shared.accessibilityDisplayShouldReduceMotion)
 }
 func applicationShouldHandleReopen(_ sender:NSApplication,hasVisibleWindows flag:Bool)->Bool{
  guard panel != nil else{return true}
  resizePanel(height:panel.frame.height,width:panel.frame.width)
  panel.makeKeyAndOrderFront(nil);NSApp.activate(ignoringOtherApps:true);return true
 }
 func applicationShouldTerminateAfterLastWindowClosed(_ sender:NSApplication)->Bool{true}
}
let app=NSApplication.shared;app.setActivationPolicy(.accessory);let controller=Controller();app.delegate=controller;app.run()
