import Capacitor

class StepsBridgeViewController: CAPBridgeViewController {
    override open func capacitorDidLoad() {
        bridge?.registerPluginInstance(StepsWatchPlugin())
    }
}
