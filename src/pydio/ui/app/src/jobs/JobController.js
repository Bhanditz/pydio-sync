(function(){

  angular.module('jobs')
       .controller('JobController', [
          'jobService', '$mdSidenav', '$mdBottomSheet', '$timeout', '$log', '$scope',
          JobController
       ]);

  /**
   * Main Controller for the Angular Material Starter App
   * @param $scope
   * @param $mdSidenav
   * @param avatarsService
   * @constructor
   */
  function JobController( jobService, $mdSidenav, $mdBottomSheet, $timeout, $log, $scope ) {
    $scope._ = window.translate;
    var self = this;

    self.selected     = null;
    self.jobList        = [ ];
    self.selectJob   = selectUser;
    self.toggleList   = toggleSideNav;
    self.makeContact  = makeContact;
    self.newSyncTask = newSyncTask;

    // Load all registered users
    self.syncing = jobService.syncing;
    self.history = jobService.history;
    self.jobs = jobService.jobs;

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
    function selectUser ( user ) {
      $scope.showAllJobs = false;
      self.selected = angular.isNumber(user) ? $scope.jobList[user] : user;
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
        $log.debug('test');
        $scope.showNewTask = !$scope.showNewTask;
    }
    window.onload = function (){ toggleSideNav(); }
  }
})();
