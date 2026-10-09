# Run on macOS before cap sync / pod install. Idempotently wires native sources
# and the SwiftUI watchOS companion into the existing Capacitor project.
require 'xcodeproj'

root = File.expand_path('../..', __dir__)
project_path = File.join(root, 'mobile/ios/App/App.xcodeproj')
project = Xcodeproj::Project.open(project_path)
app = project.targets.find { |t| t.name == 'App' } or abort 'Missing App target'
app_group = project.main_group.find_subpath('App', false) or abort 'Missing App group'
%w[StepsWatchPlugin.swift StepsBridgeViewController.swift].each do |name|
  ref = app_group.files.find { |f| f.path == name } || app_group.new_file(name)
  app.source_build_phase.add_file_reference(ref, true)
end

watch = project.targets.find { |t| t.name == 'StepsWatch' } || project.new_target(:application, 'StepsWatch', :watchos, '10.0')
group = project.main_group.find_subpath('StepsWatch', false) || project.main_group.new_group('StepsWatch', 'StepsWatch')
ref = group.files.find { |f| f.path == 'StepsWatchApp.swift' } || group.new_file('StepsWatchApp.swift')
watch.source_build_phase.add_file_reference(ref, true)
group.new_file('Info.plist') unless group.files.any? { |f| f.path == 'Info.plist' }
assets = group.files.find { |f| f.path == 'Assets.xcassets' } || group.new_file('Assets.xcassets')
watch.resources_build_phase.add_file_reference(assets, true)
app.add_dependency(watch) unless app.dependencies.any? { |d| d.target == watch }
embed = app.copy_files_build_phases.find { |p| p.name == 'Embed Watch Content' } || app.new_copy_files_build_phase('Embed Watch Content')
embed.dst_subfolder_spec = '16'
embed.dst_path = '$(CONTENTS_FOLDER_PATH)/Watch'
file = embed.add_file_reference(watch.product_reference, true)
file.settings = { 'ATTRIBUTES' => ['RemoveHeadersOnCopy'] }

version = ENV.fetch('STEPS_BUILD_NUMBER', '1')
abort 'STEPS_BUILD_NUMBER must be a positive integer' unless version.match?(/\A[1-9][0-9]*\z/)
[app, watch].each do |target|
  target.build_configurations.each do |config|
    s = config.build_settings
    s['MARKETING_VERSION'] = '2.0.0'
    s['CURRENT_PROJECT_VERSION'] = version
    s['CODE_SIGN_STYLE'] = 'Automatic'
    s['DEVELOPMENT_TEAM'] = ENV['STEPS_APPLE_TEAM_ID'] if ENV['STEPS_APPLE_TEAM_ID']
  end
end
watch.build_configurations.each do |config|
  s = config.build_settings
  s['PRODUCT_BUNDLE_IDENTIFIER'] = 'cl.stepsapp.movil.watchkitapp'
  s['INFOPLIST_FILE'] = 'StepsWatch/Info.plist'
  s['GENERATE_INFOPLIST_FILE'] = 'NO'
  s['SDKROOT'] = 'watchos'
  s['SUPPORTED_PLATFORMS'] = 'watchos watchsimulator'
  s['TARGETED_DEVICE_FAMILY'] = '4'
  s['SWIFT_VERSION'] = '5.0'
  s['SWIFT_ACTIVE_COMPILATION_CONDITIONS'] = config.name == 'Debug' ? 'DEBUG' : ''
  s['ASSETCATALOG_COMPILER_APPICON_NAME'] = 'AppIcon'
  s['SKIP_INSTALL'] = 'YES'
  s['LD_RUNPATH_SEARCH_PATHS'] = '$(inherited) @executable_path/Frameworks'
end
project.save
Xcodeproj::XCScheme.new.tap do |scheme|
  scheme.add_build_target(app)
  scheme.set_launch_target(app)
  scheme.save_as(project_path, 'Steps', true)
end
puts 'Steps iPhone + Apple Watch project prepared.'
