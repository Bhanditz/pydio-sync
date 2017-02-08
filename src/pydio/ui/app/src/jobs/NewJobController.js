
(function(){
    'use strict';
    angular
    .module('jobs')
    .factory('Ws', ['$resource',
        function($resource){
            return $resource('/ws/:job_id/', {}, {
                query: {method:'GET', params:{
                    job_id:''
                }}
            });
        }])
    .factory('Folders', ['$resource',
        function($resource){
            return $resource('/folders/:job_id/', {}, {
                query: {method:'GET', params:{
                    job_id:'',
                    url   :'',
                    ws    :'',
                    user  :'',
                    password:'',
                    subdir:''
                }, isArray:true}
            });
        }])
    .factory('EtaSize', ['$resource',
        function($resource){
            return $resource('/eta_size', {}, {
                query: {method:'GET', params:{
                    url   :'',
                    ws    :'',
                    user  :'',
                    password:'',
                    remote_folder:'',
                    local_folder: '',
                    trust_ssl:'',
                }}
            });
        }])
    .controller('NewJobController', ['jobService', '$mdDialog', '$mdSidenav', '$mdBottomSheet', '$timeout', '$log', '$scope', '$mdToast', 'Ws', 'Folders', 'Jobs', 'SelectedJobService', 'NewJobService', 'EndpointsUrl', 'EtaSize', '$filter', NewJobController]);
    /**
     * Controller for new jobs
     */
    function NewJobController( jobService, $mdDialog, $mdSidenav, mdBottomSheet, $timeout, $log, $scope, $mdToast, Ws, Folders, Jobs, SelectedJobService, NewJobService, EndpointsUrl, EtaSize, $filter ){
        // JS methods need to be exposed...
        var self = this;

        $scope.hide = function() {
            $mdDialog.hide();
        };
        $scope.cancel = function() {
            document.getElementById('welcomeDiv').style['marginTop'] = '0px';
            $mdDialog.cancel();
        };
        $scope.answer = function(answer) {
            $mdDialog.hide(answer);
        };
        $scope._ = window.translate;
        self.toggleNewJobConfig = toggleNewJobConfig;

        self.job = new Jobs();
        self.job.id              = 'new';
        self.job.frequency       = 'auto'; // auto, manual, time
        self.job.solve           = 'both'; // both, manual, local, remote
        self.job.direction       = 'bi'; // up, bi, down
        self.job.label           = 'New Job';
        self.job.hide_up_dir     = 'false'; // to hide buttons in gui
        self.job.hide_bi_dir     = 'false';  // to hide buttons in gui
        self.job.hide_down_dir   = 'false';  // to hide buttons in gui
        self.job.timeout         = '20';
        self.job.__type__        = 'JobConfig';
        $scope.ui_config = window.ui_config;
        self.job.user = "";
        self.job.password = "";
        self.job.server = "https://";
        var default_value = self.job.server;
        if(typeof(NewJobService.server) !== "undefined"){
            //console.log("FROM directive " + jobs[task].server )
            self.job.server = NewJobService.server;
        } else {
            // fetch job from existing task...
            var jobs = Jobs.query({}, function(){
                console.log(jobs)
                for (var task in jobs){
                    //console.log("FROM OLD job " + jobs[task].server )
                    if(jobs[task].server)
                        self.job.server = jobs[task].server // initialize job with first job
                    break
                }
                if (self.job.server === default_value){
                    //console.log("FROM ENDPOINT " + jobs[task].server )
                    EndpointsUrl.get({
                    }, function(response){
                        self.ws = {}
                        $scope.Content = response;

                        if (response['endpoints'] && response.endpoints.length){
                            //console.log(response)
                            pydiotheme.base = response["vanity"]["splash_bg_color"]
                            pydiotheme.accent = response["vanity"]["main_tint"]
                            pydiotheme.application_name = response["vanity"]["application_name"]
                            self.job.label = pydiotheme.application_name;
                            // angular {{}} didn't seem to work, probably suffered scope issues, deprecated
                            var item = document.getElementById('application_name');
                            if(item)
                                item.innerHTML = pydiotheme.application_name;
                            //logTheme()
                            NewJobService.server = response.endpoints[0].url;
                            self.job.server = NewJobService.server;
                            // update less
                            $scope.loading = false;
                        }
                    })
                }
              }
            )
        }

        self.job.directory = "";
        self.job.remote_folder = "/";
        self.job.total_size = 0;
        self.job.eta = 0;
        self.job.remote_size = 0;
        self.job.local_size = 0;

        self.checkedTaskFailed = false;
        self.checkedTaskFolder = true;

        $scope.SelectedJob = SelectedJobService.job;
        self.loadFolders = function(){
            $scope.loading = true;
            self.folders = Folders.query({
                job_id:'request',
                url:self.job.server,
                user:self.job.user,
                password:self.job.password,
                trust_ssl:self.job.trust_ssl?'true':'false',
                ws:self.job.workspace['@repositorySlug']
            }, function(resp){
                if(resp[0] && resp[0].error){
                    self.error = error;
                    //self.toastError(resp[0].error);
                }
                $scope.loading = false;
            }, function(resp){
                $scope.loading = false;
                self.toastError(window.translate('Error while loading folders!'));
            })
        }

        function toggleNewJobConfig(){
            $scope.showNewTask = !$scope.showNewTask; // doesn't work, wrong scope
        }

        $scope.selectedTab = 0;
        self.loadWorkspaces = function(){
            $scope.loading = true;
            if(self.job.id == 'new' && !self.job.password) {
                return false;
            }
            self.job.workspace = '';
            Ws.get({
                job_id:'request',
                url:self.job.server,
                user:self.job.user,
                password:self.job.password,
                trust_ssl:self.job.trust_ssl?'true':'false'
            }, function(response){
                if(response.application_title){
                    self.job.application_title = response.application_title;
                    $scope.application_title = self.job.application_title;
                    self.job.label = self.job.application_title;
                }
                if(response.user_display_name){
                    self.job.user_display_name = response.user_display_name;
                }
                var ret = [] // clean up response
                for (var i in response.repositories.repo){
                    if (typeof(response.repositories.repo[i]["@repositorySlug"]) !== "undefined" && response.repositories.repo[i]["@meta_syncable_REPO_SYNCABLE"] === "true" ){
                        ret.push(response.repositories.repo[i])
                    }
                }
                self.job.repositories = ret;
                $scope.loading = false;
                $scope.selectedTab = 1;
            }, function(resp){
                var error;
                if(resp.data && resp.data.error){
                    error = resp.data.error;
                } else {
                    error = "Connection problem"
                }
                self.error = error;
                //self.toastError(error)
                $scope.SSL_failed = true;
                $scope.loading = false;
            });
        };

        self.clearNewFolder = function(){
            // the following block should be factored into a clean function. #RefactorMe
            if(typeof(self.job) !== "undefined" && typeof(self.job.new_remote_folder) !== "undefined"){ // delete if exists
                var path = self.job.new_remote_folder['@filename'];
                if (path[0]== "/") // remove leading /
                    path = path.substr(1, path.length);
                var pathitems = path.split("/");
                var nextnode = {};
                for (var j in pathitems) {
                    pathitems[j] = "/" + pathitems[j];
                    if (j > 0) {
                        pathitems[j] = pathitems[j-1] + pathitems[j];
                        for (var i in nextnode['tree']){
                            if (typeof(nextnode['tree'][i]) !== "undefined" && pathitems[j] == nextnode['tree'][i]['@filename']){
                                if (pathitems.length-1 == j){
                                    nextnode['tree'].splice(i, 1);
                                } else {
                                    nextnode = nextnode['tree'][i];
                                }
                            }
                        }
                    } else {
                        var exit = false;
                        for (var i in self.folders) { // find root
                            if (self.folders[i]['@filename'] == pathitems[0]) {
                                if (pathitems.length == 1){
                                    console.log("DELETE")
                                    self.folders[i]['tree'].splice(self.folders[i]['tree'].indexOf(self.job.new_remote_folder), 1);
                                    exit = true;
                                } else {
                                    nextnode = self.folders[i];
                                }
                                break;
                            }
                        }
                        if (exit)
                            break;
                    }
                }
            }
            self.job.new_remote_folder = undefined;
        }

        self.newFolder = function (data){
            self.clearNewFolder();
            self.job.new_remote_folder = {'@filename':data['@filename'] + '/untitled folder', '@text': 'untitled folder', 'PydioSyncNewNode': true};
            // the following block should be factored into a clean function. #RefactorMe
            var path = data['@filename'];
            if (path[0]== "/") // remove leading /
                path = path.substr(1, path.length);
            var pathitems = path.split("/");
            var nextnode = {};
            for (var j in pathitems) {
                pathitems[j] = "/" + pathitems[j];
                if (j > 0) {
                    pathitems[j] = pathitems[j-1] + pathitems[j];
                    for (var i in nextnode['tree']){
                        if (typeof(nextnode['tree']) !== "undefined" && typeof(nextnode['tree'][i]) !== "undefined" && pathitems[j] == nextnode['tree'][i]['@filename']){
                            //console.log(nextnode['tree'][i]);
                            if (pathitems.length-1 == j){
                                if (typeof(nextnode['tree'][i]['tree']) === "undefined" || typeof(nextnode['tree'][i]['tree']) == Boolean){
                                    nextnode['tree'][i]['tree'] = [];
                                }
                                nextnode['tree'][i]['tree'].push(self.job.new_remote_folder);
                            } else {
                                nextnode = nextnode['tree'][i];
                            }
                        }
                    }
                } else {
                    var exit = false;
                    for (var i in self.folders) { // find root
                        if (self.folders[i]['@filename'] == pathitems[0]) {
                            if (pathitems.length == 1){
                                if (typeof(self.folders[i]['tree']) === "undefined" || typeof(self.folders[i]) == Boolean){
                                    self.folders[i]['tree'] = [];
                                }
                                self.folders[i]['tree'].push(self.job.new_remote_folder);
                                exit = true;
                            } else {
                                nextnode = self.folders[i];
                            }
                            break;
                        }
                    }
                    if (exit)
                        break;
                }
            }
        }
        $scope.pathes = {}
        self.displaySubFolders = function(path){
            /* path subfolder name to refresh how to get the parent's ?
            */
            //console.log('Fetch ls ' + path);
            $scope.loading = true;
             var subfolders = Folders.query({
                job_id:'request',
                url:self.job.server,
                user:self.job.user,
                password:self.job.password,
                trust_ssl:self.job.trust_ssl?'true':'false',
                ws:self.job.workspace['@repositorySlug'],
                subdir:path
            }, function(resp){
                //console.log(resp)
                if(resp[0] && resp[0].error){
                     self.toastError(resp[0].error);
                }
                $scope.loading = false;
                // insert the tree where it belongs... Replace an array inside an array of maps
                // the following block should be factored into a clean function. #RefactorMe
                if (path[0]== "/") // remove leading /
                    path = path.substr(1, path.length);
                var pathitems = path.split("/");
                var nextnode = {};
                for (var j in pathitems) {
                    pathitems[j] = "/" + pathitems[j];
                    if (j > 0) {
                        pathitems[j] = pathitems[j-1] + pathitems[j];
                        for (var i in nextnode['tree']){
                            if (typeof(nextnode['tree']) !== "undefined" && typeof(nextnode['tree'][i]) !== "undefined" && pathitems[j] == nextnode['tree'][i]['@filename']){
                                console.log(nextnode['tree'][i]);
                                if (pathitems.length-1 == j){
                                    nextnode['tree'][i]['tree'] = subfolders;
                                } else {
                                    nextnode = nextnode['tree'][i];
                                }
                            }
                        }
                    } else {
                        var exit = false;
                        for (var i in self.folders) { // find root
                            if (self.folders[i]['@filename'] == pathitems[0]) {
                                if (pathitems.length == 1){
                                    self.folders[i]['tree'] = subfolders;
                                    exit = true;
                                } else {
                                    nextnode = self.folders[i];
                                }
                                break;
                            }
                        }
                        if (exit)
                            break;
                    }
                }
            }, function(resp){
                $scope.loading = false;
                self.toastError(window.translate('Error while loading folders!'));
            });
        }



        self.toastError = function ( error ){
            $mdToast.show({
                      hideDelay   : 9000,
                      position    : 'bottom right',
                      controller  : function(){},
                      template    : '<md-toast><span class="md-toast-text" style="" flex>' + error + '</span></md-toast>'
                });
        }

        self.doneWithEnter = function(ev){
            if (ev.keyCode == 13 && $scope.selectedTab !== 0)
                $scope.selectedTab = Math.min(3, $scope.selectedTab + 1);
            if (ev.keyCode == 13 && $scope.selectedTab === 0){
                // trigger the behavior of the button, because of the scope and $apply can't actually call the JS
                $timeout(function(){
                    angular.element(document.getElementById("connect_button")).triggerHandler('click');
                }, 1)
            }
        }

        self.checkTask = function(){
            //console.log('Check task')
            getSizeAndEta()
            checkTaskMore()
            checkTaskFolder()
            angular.element(document.getElementById("newjoblabel")).triggerHandler('focus');
        }

        //$scope.$on('$scope.selectedTab == 3', self.checkTask()); // doesn't seem to work

        function checkTaskMore(){
            // checks that a similar task doesn't already exist
            if ($scope.selectedTab == 3){
                    var jobs = Jobs.query();
                    for (var task in jobs){
                        if ( (jobs[task]['remote_folder'] === self.job['remote_folder'] || jobs[task]['remote_folder'] + "/" === self.job['remote_folder'] ||
                             jobs[task]['remote_folder'] === self.job['remote_folder'] + "/") &&
                             jobs[task]['user'] === self.job['user'] &&
                             (jobs[task]['directory'] === self.job['directory'] || jobs[task]['directory'] +"/" === self.job['directory'] || jobs[task]['directory'] === self.job['directory'] +"/") &&
                             (jobs[task]['server'] === self.job['server'] || jobs[task]['server'] +"/" === self.job['server'] || jobs[task]['server'] === self.job['server'] +"/") &&
                             jobs[task]['workspace'] === self.job['workspace']
                            ){
                                self.checkedTaskFailed = true;
                                console.log('SIMILARITY PROBLEM')
                                console.log(jobs[task])
                                return
                            }
                    }
                    self.checkedTaskFailed = false;
            }
        }

        function checkTaskFolder(){
            if ($scope.selectedTab == 3){
                    var jobs = Jobs.query({}, function(){
                    console.log(jobs)
                    // check that a task with the same local folder doesn't exist
                    for (var task in jobs){
                        if(jobs[task].__type__ === "JobConfig"){
                            //console.log("CHECKING " + jobs[task]['directory'] + " " + self.job['directory'])
                            if (jobs[task]['directory'] === self.job['directory'] || jobs[task]['directory'] +"/" === self.job['directory'] || jobs[task]['directory'] === self.job['directory'] +"/"){
                                self.checkedTaskFolder = false;
                                console.log('FOLDER PROBLEM')
                                console.log(jobs[task]['id'] + " " + jobs[task]['directory'] + " " + self.job['directory'])
                                return
                            }
                        }
                    }
                    self.checkedTaskFolder = true;
                    });
            }
        }

        function getSizeAndEta(){
            self.loadingSizeAndEta = true;
            var info = EtaSize.query({
                url:self.job.server,
                user:self.job.user,
                password:self.job.password,
                trust_ssl:self.job.trust_ssl,
                ws:self.job.workspace['@repositorySlug'],
                remote_folder:self.job.remote_folder,
                local_folder: self.job.directory
            }, function(resp){
                if(resp[0] && resp[0].error){
                    self.error = error;
                    self.toastError(resp[0].error);
                }
                self.loadingSizeAndEta = false
                if (info.info.remote_folder_size && info.info.remote_folder_size > 0)
                    self.job.remote_size = $filter('bytes')(info.info.remote_folder_size);
                if (info.info.local_folder_size && info.info.local_folder_size > 0)
                    self.job.local_size = $filter('bytes')(info.info.local_folder_size);
                else
                    self.job.local_size = 0;
                var dl_rate = 2 * 1024 //* 1024
                var up_rate = 0.1 * 1024 //* 1024
                var eta = info.info.local_folder_size  / dl_rate + info.info.remote_folder_size / up_rate
                self.job.eta = moment.duration(eta).humanize()
            }, function(resp){
                self.loadingSizeAndEta = false;
                self.toastError(window.translate('Error while loading ETA and SIZE information!'));
            })
        }

        self.addTask = function(){
            self.checkTask()
            if (!self.checkedTaskFailed && !self.savedJOB){
                self.savedJOB = true;
                self.job.workspace = self.job.workspace['@repositorySlug'];
                delete self.job.compute_sizes;
                delete self.job.id;
                self.job.$save()
                $scope.hide()
            }
        }


    /* JS to Qt */
    if (typeof(qt) !== 'undefined'){
        new QWebChannel(qt.webChannelTransport, function(channel) {
            self.pydiouijs = channel.objects.pydiouijs;
            self.PydioQtFileDialog = channel.objects.PydioQtFileDialog;
        })
    } else { self.error2 = "UN DE FI NED"; }

    self.doStuff = function(){
        console.log('Trying to talk to Qt')
        if(self.pydiouijs.jsTrigger)
            self.pydiouijs.jsTrigger(2);

        self.PydioQtFileDialog.getDirectory();
        self.job.directory = window.PydioDirectory;
    }

     self.openDirChooser = function(ev){
        var res;
        if(!self.PydioQtFileDialog) {
            res = window.prompt(window.translate('Full path to the local folder'));
        }else{
            res = self.PydioQtFileDialog.getPath(); /* Execution of this function in Qt is asynchronous... See polling below */
        }
        self.job.directory = res;
        var pollres;
        function pollResult(){
            // poll for Folder selection finished
            if(typeof(self.job.directory) === "undefined"){
                self.PydioQtFileDialog.getDirectory()
                self.job.directory = window.PydioDirectory
                pollres = $timeout(pollResult, 700)
            }
        }
        pollResult()

     }

     }
})();

