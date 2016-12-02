(function(){
    'use strict';
    angular.module('jobs')
    .factory('GeneralConfigs', ['$resource',
        function($resource){
            return $resource('/general_configs', {}, {
                query: {method:'GET', params:{}, isArray:false}
            });
        }])
    .controller('SettingsController', ['jobService', '$mdToast', '$mdSidenav', '$mdBottomSheet', '$timeout', '$log', '$scope', '$location', 'GeneralConfigs', 'ShowGeneralSettings', SettingsController]);
    /**
     * Controller for new jobs
     */
    function SettingsController(jobService, $mdToast, $mdSidenav, mdBottomSheet, $timeout, $log, $scope, $location, GeneralConfigs, ShowGeneralSettings){
        var self = this;
        self._ = window.translate;
        if (window.ui_config){
            $scope.ui_config = window.ui_config;
        }
        // JS methods need to be exposed...
        self.SaveGeneralConfig = SaveGeneralConfig;

        // Make sur the interface is in the correct state
        ShowGeneralSettings.show = true;

        // Load the general config from agent (http://localhost:5556/general_configs)
        var general_configs_data = GeneralConfigs.query({},
            function (){
                // patch the date to get a nice display
                general_configs_data.update_info.last_update_date_FORMATTED = new Date(general_configs_data.update_info.last_update_date);
                if(general_configs_data.update_info.enable_update_check === 'true') {
                    general_configs_data.update_info.enable_update_check = true;
                }
                $scope.general_configs_data = general_configs_data;
                // path value
            }
        );
        // Post the modified general config to agent
        function SaveGeneralConfig() {
            delete general_configs_data.update_info.last_update_date_FORMATTED; // "unpatch" the date
            general_configs_data.$save();
            if (typeof($scope.ui_config) !== "undefined"){ // TODO: check proxy congig is still working
                if($scope.ui_config.login_mode === 'alias') {
                    // if proxy part is not really modified, then don't update the existing proxy settings
                    if( ($scope.proxies.http.url != "" && $scope.proxies.https.url != "") && (
                        ($scope.proxies.http.password == "" && $scope.proxies.http.username == "") ||
                        ($scope.proxies.https.password == "" && $scope.proxies.https.username == "") ||
                        ($scope.proxies.http.password != "" && $scope.proxies.http.username != "")    ||
                        ($scope.proxies.https.password != "" && $scope.proxies.https.username != "")
                        )
                    ) {
                        function cutHostPort(url, hostOrPort){
                            // removes https:// from url if present, @hostOrPort: 0 for host, 1 for port
                            url = url.replace("http://", "");
                            url = url.replace("https://", "");
                            var res = url.split(':')[hostOrPort];
                            return res == undefined ? "" : res;
                        }
                        // recover port & host from url
                        $scope.proxies.http.hostname = cutHostPort($scope.proxies.http.url, 0);
                        $scope.proxies.https.hostname = cutHostPort($scope.proxies.https.url, 0);
                        $scope.proxies.http.port = cutHostPort($scope.proxies.http.url, 1);
                        $scope.proxies.https.port = cutHostPort($scope.proxies.https.url, 1);
                        $scope.proxies.http.active = $scope.proxies.https.active;

                        // Now save the parameters
                        $scope.proxies.$save();
                    }
                    else {
                        if($scope.proxies.https.active == 'false') {
                            $scope.proxies.http.active = $scope.proxies.https.active;
                            // Now save the parameters
                            $scope.proxies.$save();
                        }
                    }
                }
            }
            $mdToast.show({
                hideDelay   : 4000,
                position    : 'bottom right',
                controller  : function(){},
                template    : '<md-toast><span class="md-toast-text" style="" flex>' + window.translate('Settings Updated') + '</span></md-toast>'
            });
        }
        if (typeof(qt) !== 'undefined'){
            new QWebChannel(qt.webChannelTransport, function(channel) {
                self.pydiouijs = channel.objects.pydiouijs;
                self.PydioQtFileDialog = channel.objects.PydioQtFileDialog;
            })
        } else { self.error2 = "UN DE FI NED"; }

        self.openLogs = function(){
            if(!self.PydioQtFileDialog)
                alert("Can't open logs without Qt.");
            else {
                self.PydioQtFileDialog.openLogs();
            }

        }
    }
})();
