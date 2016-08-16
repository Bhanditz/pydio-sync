(function(){

  angular.module('jobs', ['ngResource'])
        .factory('Jobs', ['$resource',
            function($resource){
                return $resource('/jobs/:job_id/', {}, {
                    query: {method:'GET', params:{job_id:''}, isArray:true}
                });
        }])
        .filter('bytes', function() {
        return function(bytes, precision) {
            if (bytes == 0) return bytes;
            if (isNaN(parseFloat(bytes)) || !isFinite(bytes)) return bytes;
            if (typeof precision === 'undefined') precision = 1;
            var units = ['bytes', 'kB', 'MB', 'GB', 'TB', 'PB'],
                number = Math.floor(Math.log(bytes) / Math.log(1024));
            return (bytes / Math.pow(1024, Math.floor(number))).toFixed(precision) +  ' ' + units[number];
        }
        })
       .filter('twoLetters', function(){
            // Fancy two letter somewhat random extractor my-files -> MF
            return function(input){
                if(typeof(input) === "undefined")
                    return "?¿"
                var output;
                var pos = input.indexOf('-')
                if ( pos > -1 && input.length > pos+1){
                    output = (input[0] + input[pos+1]).toUpperCase()
                } else {
                    if (input.length >= 2)
                        output = input.substr(0, 2).toUpperCase()
                    else
                        output = input.substr(0, 2).toUpperCase()
                }
                return output
            }
       })
       .factory('Commands', ['$resource',
            function($resource){
                return $resource('/cmd/:cmd/:job_id', {}, {
                    query: {method:'GET', params:{job_id:''}, isArray:true}
                });
            }])
       .controller('JobController', [
          'jobService', '$mdSidenav', '$mdBottomSheet', '$timeout', '$log', '$scope', 'Jobs', 'Commands',
          JobController
       ])

  /**
   * Main Controller for the Angular Material Starter App
   * @param $scope
   * @param $mdSidenav
   * @param avatarsService
   * @constructor
   */
  function JobController( jobService, $mdSidenav, $mdBottomSheet, $timeout, $log, $scope, Jobs, Commands ) {
    $scope._ = window.translate;
    var self = this;

    self.selected     = null;
    self.selectJob   = selectJob;
    self.toggleList   = toggleSideNav;
    self.makeContact  = makeContact;
    self.newSyncTask = newSyncTask;
    self.changeSelected = changeSelected;
    self.toggleGeneralSettings = toggleGeneralSettings;

    // Load all jobs
    self.syncing = jobService.syncing;
    self.history = jobService.history;
    $scope.pathes = {};
    $scope.jobs = Jobs.query();
    self.jobs = $scope.jobs;

    /*
    self.jobList        = [ ];
    jobService.loadJobList().then(
        function( jobList ) {
            self.jobList    = [].concat(jobList);
            self.selected = jobList[0];
        }
    );
    jobService.loadAllJobs().then(
        function(jobs){
            self.jobs = jobs;
        }
    );
    */
    // *********************************
    // Internal methods
    // *********************************

    /**
     * Hide or Show the 'left' sideNav area
     */
    function toggleSideNav() {
      $mdSidenav('left').toggle();
    }

    /**
     * Select the current avatars
     * @param menuId
     */
    function selectJob ( user ) {
      $scope.showAllJobs = false;
      self.selected = angular.isNumber(user) ? $scope.jobs[user] : user;
      $scope.selected = self.selected; // hack to pass info around...
    }
    self.showJobs = function(){
        $scope.showAllJobs = true;
    }
    /**
     * Show the Contact view in the bottom sheet
     */
    function makeContact(selectedUser) {

        $mdBottomSheet.show({
          controllerAs  : "vm",
          templateUrl   : './src/users/view/listjob.html',
          controller    : [ '$mdBottomSheet', JobListController],
          parent        : angular.element(document.getElementById('content'))
        }).then(function(clickedItem) {
          $log.debug( clickedItem.name + ' clicked!');
        });

        /**
         * User ContactSheet controller
         */
        function JobListController( $mdBottomSheet ) {
          this.user = selectedUser;
          this.contactUser = function(action) {
            // The actually contact process has not been implemented...
            // so just hide the bottomSheet

            $mdBottomSheet.hide(action);
          };
        }
    }
    jobService.currentNavItem = 'history';
    function newSyncTask(){
        $scope.showNewTask = !$scope.showNewTask;
        $scope.showAllJobs = false;
        $scope.showGeneralSettings = false;
    }
    window.onload = function (){
        //toggleSideNav();
        if ($scope.jobs.length == 1)
            changeSelected(0);
        else $scope.showAllJobs = true;
    }

    /**
        $scope toggles, bad practice probably
    */
    function changeSelected(item){
        selectJob(item);
    }

    function toggleGeneralSettings(){
        $scope.showGeneralSettings = !$scope.showGeneralSettings;
    }

    $scope.applyCmd = function(cmd){
        Commands.query({cmd:cmd, job_id:$scope.selected.id}, function(){
            var newJobs = Jobs.query({}, function(){
                $scope.jobs = newJobs;
            });
        });
    }
  }
})();
