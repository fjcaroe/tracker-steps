import Capacitor
import WatchConnectivity

/// Only presentation snapshots and navigation requests cross this bridge.
final class StepsWatchSession: NSObject, WCSessionDelegate {
    static let shared = StepsWatchSession()
    weak var plugin: StepsWatchPlugin?
    private var snapshot: [String: Any] = ["version": 1, "state": "locked", "scope": "", "company": "", "modules": [], "pending": 0, "problems": 0, "syncing": false, "demo": false, "issuedAt": Date().timeIntervalSince1970 * 1000, "validUntil": 0]

    func start() {
        guard WCSession.isSupported() else { return }
        WCSession.default.delegate = self
        WCSession.default.activate()
    }

    func publish(_ value: [String: Any]) throws {
        snapshot = value
        guard WCSession.isSupported(), WCSession.default.activationState == .activated else { return }
        try WCSession.default.updateApplicationContext(snapshot)
        if WCSession.default.isReachable {
            WCSession.default.sendMessage(["snapshot": snapshot], replyHandler: nil, errorHandler: { _ in })
        }
    }

    func session(_ session: WCSession, activationDidCompleteWith activationState: WCSessionActivationState, error: Error?) {
        DispatchQueue.main.async { try? self.publish(self.snapshot) }
    }
    func sessionDidBecomeInactive(_ session: WCSession) {}
    func sessionDidDeactivate(_ session: WCSession) { session.activate() }
    func session(_ session: WCSession, didReceiveMessage message: [String: Any], replyHandler: @escaping ([String: Any]) -> Void) {
        DispatchQueue.main.async {
            if message["request"] as? String == "refresh" { replyHandler(["snapshot": self.snapshot]); return }
            guard message["request"] as? String == "openModule",
                  let module = message["module"] as? String, let scope = message["scope"] as? String,
                  self.snapshot["state"] as? String == "ready", scope == self.snapshot["scope"] as? String,
                  let until = self.snapshot["validUntil"] as? Double, until > Date().timeIntervalSince1970 * 1000,
                  let modules = self.snapshot["modules"] as? [[String: String]], modules.contains(where: { $0["id"] == module }),
                  let plugin = self.plugin else { replyHandler(["accepted": false]); return }
            plugin.notifyListeners("openModule", data: ["module": module, "scope": scope])
            replyHandler(["accepted": true])
        }
    }
}

@objc(StepsWatchPlugin)
public class StepsWatchPlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "StepsWatchPlugin"
    public let jsName = "StepsWatch"
    public let pluginMethods: [CAPPluginMethod] = [CAPPluginMethod(name: "publish", returnType: CAPPluginReturnPromise)]
    public override func load() { StepsWatchSession.shared.plugin = self }
    @objc func publish(_ call: CAPPluginCall) {
        guard let value = call.getObject("snapshot"), value["version"] as? Int == 1 else {
            call.reject("Invalid watch snapshot"); return
        }
        DispatchQueue.main.async {
            do { try StepsWatchSession.shared.publish(value); call.resolve() }
            catch { call.reject("Watch context unavailable") }
        }
    }
}
