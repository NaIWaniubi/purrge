// Purrge 原生提醒窗（macOS NSAlert，JXA）。用法：
// osascript -l JavaScript alert.js <剩余文本> <总容量文本> <阈值文本> <已用比例0-1> <图标路径>
// 输出：scan（帮我看看）/ later（等会儿再说）
ObjC.import("AppKit");

function run(argv) {
  const [freeTxt, totalTxt, thTxt, usedFrac, iconPath] = argv;
  const used = Math.max(0, Math.min(1, parseFloat(usedFrac) || 0));
  const app = $.NSApplication.sharedApplication;
  app.setActivationPolicy($.NSApplicationActivationPolicyAccessory);
  app.activateIgnoringOtherApps(true);

  const alert = $.NSAlert.alloc.init;
  alert.messageText = $(`主人，磁盘只剩 ${freeTxt} 了`);
  alert.informativeText = $(`已经低于你定的 ${thTxt} 啦。要我帮你翻翻哪些能清掉吗？
删哪些，你说了算 🐾`);
  alert.addButtonWithTitle($("帮我看看"));
  alert.addButtonWithTitle($("等会儿再说"));
  const img = $.NSImage.alloc.initWithContentsOfFile($(iconPath));
  if (img && !img.isNil()) alert.icon = img;

  // 附加视图：磁盘用量条 + 说明
  const W = 300;
  const view = $.NSView.alloc.initWithFrame($.NSMakeRect(0, 0, W, 46));
  const bar = $.NSProgressIndicator.alloc.initWithFrame($.NSMakeRect(0, 22, W, 16));
  bar.style = 0; // bar
  bar.indeterminate = false;
  bar.minValue = 0;
  bar.maxValue = 100;
  bar.doubleValue = used * 100;
  view.addSubview(bar);
  const label = $.NSTextField.labelWithString($(`已用 ${Math.round(used * 100)}%  ·  总容量 ${totalTxt}`));
  label.frame = $.NSMakeRect(0, 0, W, 16);
  label.font = $.NSFont.systemFontOfSize(11);
  label.textColor = $.NSColor.secondaryLabelColor;
  view.addSubview(label);
  alert.accessoryView = view;

  alert.window.level = $.NSFloatingWindowLevel;
  const res = alert.runModal;
  return res === 1000 ? "scan" : "later"; // NSAlertFirstButtonReturn
}
